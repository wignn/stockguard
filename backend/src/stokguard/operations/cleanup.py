from __future__ import annotations

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.maintenance import maintenance_status, wait_for_drain
from stokguard.files.models import EvidenceFile


class CleanupPreview(BaseModel):
    orphan_paths: list[str]
    total_bytes: int
    preview_token: str


class CleanupReport(BaseModel):
    removed_count: int
    removed_paths: list[str]


def _scan_orphans(settings: Settings) -> CleanupPreview:
    evidence_root = (settings.data_dir / "evidence").resolve()
    if not evidence_root.exists():
        return CleanupPreview(
            orphan_paths=[],
            total_bytes=0,
            preview_token=hashlib.sha256(b"empty").hexdigest(),
        )

    engine = make_engine(settings.database_path)
    try:
        with Session(engine) as db:
            tracked_keys = set(db.scalars(select(EvidenceFile.storage_key)).all())
    finally:
        engine.dispose()

    tracked_resolved = {(evidence_root / key).resolve() for key in tracked_keys}
    orphan_rels: list[str] = []
    total_bytes = 0
    token_hasher = hashlib.sha256()

    for file_path in sorted(evidence_root.rglob("*")):
        if not file_path.is_file():
            continue
        if file_path.resolve() not in tracked_resolved:
            rel = file_path.resolve().relative_to(evidence_root).as_posix()
            size = file_path.stat().st_size
            orphan_rels.append(rel)
            total_bytes += size
            token_hasher.update(f"{rel}:{size}\n".encode())

    preview = CleanupPreview(
        orphan_paths=orphan_rels,
        total_bytes=total_bytes,
        preview_token=token_hasher.hexdigest(),
    )
    maint_dir = settings.data_dir / ".maintenance"
    maint_dir.mkdir(parents=True, exist_ok=True)
    (maint_dir / "cleanup_preview.json").write_text(
        json.dumps(preview.model_dump(), indent=2), encoding="utf-8"
    )
    return preview


def preview_cleanup(settings: Settings) -> CleanupPreview:
    return _scan_orphans(settings)


def apply_cleanup(settings: Settings, preview_token: str) -> CleanupReport:
    if not maintenance_status(settings)["active"]:
        raise ValueError("Mode pemeliharaan wajib aktif sebelum menghapus berkas bukti yatim.")
    wait_for_drain(settings)
    current = _scan_orphans(settings)
    if not preview_token or current.preview_token != preview_token:
        raise ValueError(
            "Token pratinjau tidak cocok atau daftar berkas berubah; "
            "jalankan cleanup --preview kembali."
        )

    evidence_root = (settings.data_dir / "evidence").resolve()
    removed: list[str] = []
    for rel in current.orphan_paths:
        target = (evidence_root / Path(*rel.split("/"))).resolve()
        if evidence_root in target.parents and target.is_file():
            target.unlink(missing_ok=True)
            removed.append(rel)

    return CleanupReport(removed_count=len(removed), removed_paths=removed)
