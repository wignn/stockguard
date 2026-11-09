from __future__ import annotations

import hashlib
import json
import shutil
import sqlite3
import tarfile
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

from pydantic import BaseModel
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.maintenance import maintenance_drain_scope
from stokguard.files.models import EvidenceFile
from stokguard.files.storage import content_path


class EvidenceManifestEntry(BaseModel):
    id: str
    storage_key: str
    sha256: str
    size_bytes: int
    mime_type: str


class BackupManifest(BaseModel):
    created_at: str
    schema_revision: str
    database_sha256: str
    database_size_bytes: int
    evidence_files: list[EvidenceManifestEntry]
    config: dict[str, str | bool]


def sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    total = 0
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
            total += len(chunk)
    return digest.hexdigest(), total


def create_backup(settings: Settings, destination: Path) -> BackupManifest:
    destination = destination.expanduser().resolve()
    if destination.exists():
        raise ValueError("Berkas tujuan backup sudah ada; pilih nama berkas baru.")
    destination.parent.mkdir(parents=True, exist_ok=True)

    with maintenance_drain_scope(settings, reason="backup"):
        with TemporaryDirectory(prefix="backup-stage-", dir=destination.parent) as temp_dir:
            stage_root = Path(temp_dir)
            staged_db = stage_root / "stokguard.db"

            # Use SQLite online backup API to produce a consistent single-file snapshot
            src_conn = sqlite3.connect(str(settings.database_path))
            dst_conn = sqlite3.connect(str(staged_db))
            try:
                src_conn.backup(dst_conn)
            finally:
                dst_conn.close()
                src_conn.close()

            db_sha256, db_size = sha256_file(staged_db)

            engine = make_engine(staged_db)
            try:
                with Session(engine) as db:
                    revision = db.scalar(text("SELECT version_num FROM alembic_version")) or ""
                    files = db.scalars(
                        select(EvidenceFile).order_by(EvidenceFile.created_at, EvidenceFile.id)
                    ).all()
                    evidence_entries: list[EvidenceManifestEntry] = []
                    evidence_stage = stage_root / "evidence"
                    evidence_stage.mkdir(parents=True, exist_ok=True)
                    for item in files:
                        src_path = content_path(settings.data_dir / "evidence", item.storage_key)
                        if not src_path.exists():
                            raise ValueError(
                                f"Berkas bukti {item.storage_key} tidak ditemukan di disk."
                            )
                        file_sha, file_size = sha256_file(src_path)
                        if file_sha != item.sha256 or file_size != item.size_bytes:
                            raise ValueError(
                                f"Integritas berkas bukti {item.storage_key} "
                                "tidak cocok dengan database."
                            )
                        dst_path = evidence_stage / src_path.name
                        dst_path.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copy2(src_path, dst_path)
                        evidence_entries.append(
                            EvidenceManifestEntry(
                                id=item.id,
                                storage_key=item.storage_key,
                                sha256=file_sha,
                                size_bytes=file_size,
                                mime_type=item.mime_type,
                            )
                        )
            finally:
                engine.dispose()

            manifest = BackupManifest(
                created_at=datetime.now(UTC).isoformat(),
                schema_revision=str(revision),
                database_sha256=db_sha256,
                database_size_bytes=db_size,
                evidence_files=evidence_entries,
                config={
                    "ocr_languages": settings.ocr_languages,
                    "secure_cookies": settings.secure_cookies,
                },
            )
            manifest_path = stage_root / "manifest.json"
            manifest_path.write_text(json.dumps(manifest.model_dump(), indent=2), encoding="utf-8")

            part_archive = destination.with_name(f".{destination.name}.part")
            try:
                with tarfile.open(part_archive, "w:gz") as tar:
                    tar.add(manifest_path, arcname="manifest.json")
                    tar.add(staged_db, arcname="stokguard.db")
                    if (stage_root / "evidence").exists():
                        tar.add(stage_root / "evidence", arcname="evidence")
                part_archive.replace(destination)
            except BaseException:
                part_archive.unlink(missing_ok=True)
                raise

    return manifest
