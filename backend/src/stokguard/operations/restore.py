from __future__ import annotations

import json
import shutil
import sqlite3
import tarfile
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from alembic.config import Config
from alembic.script import ScriptDirectory
from pydantic import BaseModel
from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from stokguard.auth.models import AuthSession
from stokguard.core.db import make_engine
from stokguard.core.transactions import write_uow
from stokguard.files.models import EvidenceFile, EvidenceLink
from stokguard.files.storage import content_path
from stokguard.inventory.models import StockBalance, StockMovement
from stokguard.ocr.models import OcrJob
from stokguard.operations.backup import BackupManifest, sha256_file


class RestoreReport(BaseModel):
    ok: bool
    schema_revision: str
    revoked_sessions: int
    requeued_jobs: int
    evidence_files: int


def _expected_head_revisions() -> set[str]:
    root = Path(__file__).resolve().parents[3]
    script = ScriptDirectory.from_config(Config(str(root / "alembic.ini")))
    return set(script.get_heads())


def _validate_tar_member(member: tarfile.TarInfo, stage_root: Path) -> Path:
    if member.issym() or member.islnk() or member.ischr() or member.isblk() or member.isfifo():
        raise ValueError("Path tidak aman: tautan simbolik atau berkas khusus ditolak.")
    posix = PurePosixPath(member.name)
    if posix.is_absolute() or ".." in posix.parts or any(p.startswith("\\") for p in posix.parts):
        raise ValueError(f"Path tidak aman di dalam arsip: {member.name}")
    resolved = (stage_root / Path(*posix.parts)).resolve()
    if resolved != stage_root and stage_root not in resolved.parents:
        raise ValueError(f"Path tidak aman di luar direktori tujuan: {member.name}")
    return resolved


def restore_backup(archive: Path, destination: Path) -> RestoreReport:
    archive = archive.expanduser().resolve()
    destination = destination.expanduser().resolve()
    if not archive.exists():
        raise ValueError("Berkas arsip backup tidak ditemukan.")
    if destination.exists() and (not destination.is_dir() or any(destination.iterdir())):
        raise ValueError("Tujuan restore harus direktori baru atau kosong.")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix="restore-stage-", dir=destination.parent) as temp_dir:
        stage_root = Path(temp_dir).resolve()
        with tarfile.open(archive, "r:gz") as tar:
            members = tar.getmembers()
            for member in members:
                target_path = _validate_tar_member(member, stage_root)
                if member.isdir():
                    target_path.mkdir(parents=True, exist_ok=True)
                elif member.isfile():
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    extracted = tar.extractfile(member)
                    if extracted is None:
                        raise ValueError("Gagal membaca anggota arsip backup.")
                    with extracted, target_path.open("wb") as out_handle:
                        shutil.copyfileobj(extracted, out_handle)
                else:
                    raise ValueError("Tipe anggota arsip tidak didukung.")

        manifest_file = stage_root / "manifest.json"
        staged_db = stage_root / "stokguard.db"
        if not manifest_file.exists() or not staged_db.exists():
            raise ValueError("Arsip backup tidak lengkap (manifest atau database hilang).")

        manifest = BackupManifest.model_validate(
            json.loads(manifest_file.read_text(encoding="utf-8"))
        )
        actual_db_sha, actual_db_size = sha256_file(staged_db)
        if (
            actual_db_sha != manifest.database_sha256
            or actual_db_size != manifest.database_size_bytes
        ):
            raise ValueError("Hash berkas tidak cocok untuk database SQLite.")

        expected_heads = _expected_head_revisions()
        if expected_heads and manifest.schema_revision not in expected_heads:
            raise ValueError("Revisi skema arsip tidak kompatibel dengan versi aplikasi ini.")

        evidence_root = stage_root / "evidence"
        evidence_root.mkdir(parents=True, exist_ok=True)
        expected_paths: set[Path] = set()
        for entry in manifest.evidence_files:
            file_path = content_path(evidence_root, entry.storage_key)
            if not file_path.exists():
                raise ValueError(f"Berkas bukti {entry.storage_key} hilang dari arsip.")
            file_sha, file_size = sha256_file(file_path)
            if file_sha != entry.sha256 or file_size != entry.size_bytes:
                raise ValueError(f"Hash berkas tidak cocok untuk bukti {entry.storage_key}.")
            expected_paths.add(file_path.resolve())

        for disk_file in evidence_root.rglob("*"):
            if disk_file.is_file() and disk_file.resolve() not in expected_paths:
                raise ValueError("Arsip mengandung berkas bukti yang tidak terdaftar di manifest.")

        # Run SQLite PRAGMA integrity_check and foreign_key_check
        conn = sqlite3.connect(str(staged_db))
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchall()
            if integrity != [("ok",)]:
                raise ValueError("Pemeriksaan integritas SQLite gagal.")
            fk_issues = conn.execute("PRAGMA foreign_key_check").fetchall()
            if fk_issues:
                raise ValueError("Pemeriksaan foreign key SQLite gagal.")
        finally:
            conn.close()

        engine = make_engine(staged_db)
        try:
            with Session(engine) as db:
                db_rev = db.scalar(text("SELECT version_num FROM alembic_version")) or ""
                if str(db_rev) != manifest.schema_revision:
                    raise ValueError("Revisi skema di dalam database tidak sesuai manifest.")

                # Verify ledger balance consistency for every StockBalance row
                balances = db.scalars(select(StockBalance)).all()
                for bal in balances:
                    ledger_sum = db.scalar(
                        select(func.coalesce(func.sum(StockMovement.quantity_milli), 0)).where(
                            StockMovement.business_id == bal.business_id,
                            StockMovement.product_id == bal.product_id,
                            StockMovement.location_id == bal.location_id,
                        )
                    )
                    if int(ledger_sum or 0) != bal.quantity_milli:
                        raise ValueError(
                            f"Saldo produk {bal.product_id} tidak konsisten dengan buku mutasi."
                        )

                # Verify all DB EvidenceFile rows match manifest and links point to valid files
                db_files = db.scalars(select(EvidenceFile)).all()
                manifest_by_id = {item.id: item for item in manifest.evidence_files}
                if len(db_files) != len(manifest_by_id):
                    raise ValueError("Jumlah berkas bukti di database tidak sesuai manifest.")
                for db_file in db_files:
                    m_entry = manifest_by_id.get(db_file.id)
                    if (
                        m_entry is None
                        or m_entry.sha256 != db_file.sha256
                        or m_entry.storage_key != db_file.storage_key
                    ):
                        raise ValueError("Metadata berkas bukti tidak konsisten dengan manifest.")

                links = db.scalars(select(EvidenceLink)).all()
                for link in links:
                    if link.file_id not in manifest_by_id:
                        raise ValueError("Tautan bukti merujuk ke berkas yang tidak ada.")

            # Revoke sessions and invalidate OCR leases before workers claim fresh tokens.
            revoked_count = 0
            requeued_count = 0
            with write_uow(engine) as db:
                sessions = db.scalars(select(AuthSession)).all()
                for sess in sessions:
                    if not sess.revoked:
                        revoked_count += 1
                    sess.revoked = True

                jobs = db.scalars(select(OcrJob).where(OcrJob.status == "processing")).all()
                for job in jobs:
                    job.status = "queued"
                    job.lease_expires_at = None
                    job.fencing_token = None
                    requeued_count += 1
        finally:
            engine.dispose()

        destination.mkdir(parents=True, exist_ok=True)
        shutil.move(str(staged_db), str(destination / "stokguard.db"))
        shutil.move(str(evidence_root), str(destination / "evidence"))

    return RestoreReport(
        ok=True,
        schema_revision=manifest.schema_revision,
        revoked_sessions=revoked_count,
        requeued_jobs=requeued_count,
        evidence_files=len(manifest.evidence_files),
    )
