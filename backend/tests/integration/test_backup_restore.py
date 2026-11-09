import io
import json
import tarfile
import threading
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import select
from sqlalchemy.orm import Session
from typer.testing import CliRunner

from stokguard.auth.models import AuthSession
from stokguard.businesses.models import Business
from stokguard.cli import cli
from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.maintenance import (
    disable_maintenance,
    enable_maintenance,
    maintenance_status,
    operation_slot,
)
from stokguard.files.models import EvidenceFile
from stokguard.inventory.models import StockBalance
from stokguard.ocr.engine import OcrText
from stokguard.ocr.models import OcrJob
from stokguard.ocr.worker import process_one, run_worker
from stokguard.operations.backup import create_backup
from stokguard.operations.cleanup import apply_cleanup, preview_cleanup
from stokguard.operations.restore import restore_backup


@pytest.fixture(autouse=True)
def migration_revision(app, monkeypatch):
    from alembic import command
    from alembic.config import Config

    monkeypatch.setenv("STOKGUARD_DATA_DIR", str(app.state.settings.data_dir))
    config = Config(str(Path(__file__).resolve().parents[2] / "alembic.ini"))
    command.stamp(config, "head")


@pytest.fixture
def owner_headers(authenticated):
    return {"X-CSRF-Token": authenticated.headers["X-CSRF-Token"]}


@pytest.fixture
def business_id(app):
    return app.state.test_business_id


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (4, 4), color=(10, 40, 90)).save(buf, format="PNG")
    return buf.getvalue()


def test_backup_blocks_new_mutations_and_waits_for_inflight_upload(
    client: TestClient, owner_headers, business_id, app
):
    settings: Settings = app.state.settings

    # Enable maintenance mode and verify API mutations and login are rejected with 503
    enable_maintenance(settings, reason="uji maintenance")
    assert maintenance_status(settings)["active"] is True

    mut_res = client.post(
        f"/api/v1/businesses/{business_id}/products",
        headers=owner_headers,
        json={"sku": "MNT-01", "name": "Produk Maintenance", "unit": "pcs", "cost_rupiah": "5000"},
    )
    assert mut_res.status_code == 503
    assert mut_res.json()["error"]["code"] == "maintenance_mode"

    upload_res = client.post(
        f"/api/v1/businesses/{business_id}/files",
        headers=owner_headers,
        files={"file": ("nota.png", _png_bytes(), "image/png")},
    )
    assert upload_res.status_code == 503

    login_res = client.post(
        "/api/v1/auth/login",
        json={"username": "owner", "password": "owner-password-123"},
    )
    assert login_res.status_code == 503

    # GET requests remain available during maintenance
    get_res = client.get(
        f"/api/v1/businesses/{business_id}/products",
        headers=owner_headers,
    )
    assert get_res.status_code == 200

    disable_maintenance(settings)
    assert maintenance_status(settings)["active"] is False

    # Now simulate an in-flight upload holding an operation slot while create_backup starts
    entered = threading.Event()
    release = threading.Event()
    events: list[str] = []

    def inflight_writer():
        with operation_slot(settings, "upload"):
            entered.set()
            release.wait(timeout=5.0)
            events.append("upload_finished")

    worker_thread = threading.Thread(target=inflight_writer)
    worker_thread.start()
    assert entered.wait(timeout=2.0)

    archive_path = settings.data_dir.parent / "backup-inflight.tar.gz"
    backup_done = threading.Event()

    def run_backup():
        create_backup(settings, archive_path)
        events.append("backup_finished")
        backup_done.set()

    backup_thread = threading.Thread(target=run_backup)
    backup_thread.start()
    time.sleep(0.15)
    assert not backup_done.is_set(), "Backup must wait for in-flight operation slot to drain"

    release.set()
    worker_thread.join(timeout=5.0)
    backup_thread.join(timeout=5.0)
    assert backup_done.is_set()
    assert events == ["upload_finished", "backup_finished"]
    assert archive_path.exists()
    assert maintenance_status(settings)["active"] is False


def test_worker_pauses_without_partial_result(client: TestClient, owner_headers, business_id, app):
    settings: Settings = app.state.settings
    upload_res = client.post(
        f"/api/v1/businesses/{business_id}/files",
        headers=owner_headers,
        files={"file": ("nota-worker.png", _png_bytes(), "image/png")},
    )
    assert upload_res.status_code == 201
    file_id = upload_res.json()["id"]

    job_res = client.post(
        f"/api/v1/businesses/{business_id}/ocr-jobs",
        headers=owner_headers,
        json={"file_id": file_id},
    )
    assert job_res.status_code == 201
    job_id = job_res.json()["id"]

    class DummyEngine:
        def available(self) -> bool:
            return True

        def recognize(self, path: Path, timeout_seconds: int) -> OcrText:
            return OcrText(text="NOTA-01\nSusu 2 5000")

    enable_maintenance(settings, reason="worker pause test")
    stop = threading.Event()
    worker_thread = threading.Thread(target=run_worker, args=(settings, DummyEngine(), stop))
    worker_thread.start()
    try:
        deadline = time.time() + 3.0
        paused_ack = False
        while time.time() < deadline:
            status = maintenance_status(settings)
            if status.get("worker_paused"):
                paused_ack = True
                break
            time.sleep(0.05)
        assert paused_ack is True

        # Job must still be queued (not claimed or partially processed during maintenance)
        assert process_one(settings, DummyEngine()) is False
        with Session(app.state.engine) as db:
            job = db.get(OcrJob, job_id)
            assert job.status == "queued"
    finally:
        stop.set()
        worker_thread.join(timeout=3.0)
        disable_maintenance(settings)


def test_restore_ledger_files_jobs_consistent(
    client: TestClient, owner_headers, business_id, app, tmp_path
):
    settings: Settings = app.state.settings

    # Build ledger history, linked evidence and an interrupted OCR job.
    prod = client.post(
        f"/api/v1/businesses/{business_id}/products",
        headers=owner_headers,
        json={
            "sku": "RST-01",
            "name": "Beras Restore",
            "unit": "kg",
            "step_quantity": "1",
            "cost_rupiah": "14000",
        },
    ).json()
    mov1 = client.post(
        f"/api/v1/businesses/{business_id}/movements",
        headers={**owner_headers, "Idempotency-Key": "00000000-0000-4000-8000-000000000801"},
        json={
            "product_id": prod["id"],
            "kind": "opening",
            "quantity": "20",
            "occurred_at": "2026-11-09T08:00:00Z",
            "note": "Stok awal restore",
            "expected_balance_version": 0,
        },
    ).json()
    client.post(
        f"/api/v1/businesses/{business_id}/movements",
        headers={**owner_headers, "Idempotency-Key": "00000000-0000-4000-8000-000000000802"},
        json={
            "product_id": prod["id"],
            "kind": "sale",
            "quantity": "5",
            "occurred_at": "2026-11-09T08:00:00Z",
            "note": "Penjualan restore",
            "expected_balance_version": 1,
        },
    )

    ev = client.post(
        f"/api/v1/businesses/{business_id}/files",
        headers=owner_headers,
        files={"file": ("bukti-restore.png", _png_bytes(), "image/png")},
    ).json()
    link_res = client.post(
        f"/api/v1/businesses/{business_id}/movements/{mov1['id']}/evidence",
        headers=owner_headers,
        json={"file_id": ev["id"]},
    )
    assert link_res.status_code == 201

    job_res = client.post(
        f"/api/v1/businesses/{business_id}/ocr-jobs",
        headers=owner_headers,
        json={"file_id": ev["id"]},
    ).json()

    # Simulate an OCR job stuck in processing when backup runs
    with Session(app.state.engine) as db:
        job = db.get(OcrJob, job_res["id"])
        job.status = "processing"
        job.lease_expires_at = "2026-11-09T12:00:00+00:00"
        job.fencing_token = "pre-backup-lease"
        db.commit()

    archive_path = tmp_path / "stokguard-backup.tar.gz"
    manifest = create_backup(settings, archive_path)
    assert archive_path.exists()
    assert manifest.schema_revision
    assert len(manifest.evidence_files) == 1
    assert "password" not in json.dumps(manifest.model_dump()).casefold()

    # Reject restoring into an existing non-empty directory
    non_empty = tmp_path / "already-exists"
    non_empty.mkdir()
    (non_empty / "existing.txt").write_text("jangan ditimpa")
    with pytest.raises(ValueError, match="Tujuan restore harus direktori baru atau kosong"):
        restore_backup(archive_path, non_empty)

    # Restore into a fresh directory
    restored_dir = tmp_path / "restored-data"
    report = restore_backup(archive_path, restored_dir)
    assert report.ok is True
    assert report.revoked_sessions >= 1
    assert report.requeued_jobs == 1

    restored_engine = make_engine(restored_dir / "stokguard.db")
    try:
        with Session(restored_engine) as db:
            bal = db.scalar(select(StockBalance).where(StockBalance.product_id == prod["id"]))
            assert bal is not None
            assert bal.quantity_milli == 15_000

            sessions = db.scalars(select(AuthSession)).all()
            assert sessions and all(s.revoked is True for s in sessions)

            restored_job = db.get(OcrJob, job_res["id"])
            assert restored_job is not None
            assert restored_job.status == "queued"
            assert restored_job.lease_expires_at is None
            assert restored_job.fencing_token is None

            restored_file = db.get(EvidenceFile, ev["id"])
            assert restored_file is not None
            assert (restored_dir / "evidence" / restored_file.storage_key).exists()
    finally:
        restored_engine.dispose()


def test_tampered_or_path_traversal_archive_rejected(
    client: TestClient, owner_headers, business_id, app, tmp_path
):
    settings: Settings = app.state.settings
    client.post(
        f"/api/v1/businesses/{business_id}/files",
        headers=owner_headers,
        files={"file": ("bukti.png", _png_bytes(), "image/png")},
    )
    valid_archive = tmp_path / "valid.tar.gz"
    create_backup(settings, valid_archive)

    # 1. Create an archive with path traversal member "../evil.txt"
    traversal_archive = tmp_path / "traversal.tar.gz"
    with tarfile.open(traversal_archive, "w:gz") as tar:
        info = tarfile.TarInfo(name="../evil.txt")
        payload = b"evil"
        info.size = len(payload)
        tar.addfile(info, io.BytesIO(payload))

    target1 = tmp_path / "target-traversal"
    with pytest.raises(ValueError, match="Path tidak aman"):
        restore_backup(traversal_archive, target1)
    assert not (tmp_path / "evil.txt").exists()

    # 2. Tamper with evidence file bytes inside a copy of valid_archive
    extract_dir = tmp_path / "tamper-work"
    extract_dir.mkdir()
    with tarfile.open(valid_archive, "r:gz") as tar:
        tar.extractall(extract_dir, filter="data")
    for p in (extract_dir / "evidence").rglob("*"):
        if p.is_file():
            p.write_bytes(b"corrupted-bytes")
    tampered_archive = tmp_path / "tampered.tar.gz"
    with tarfile.open(tampered_archive, "w:gz") as tar:
        for item in extract_dir.iterdir():
            tar.add(item, arcname=item.name)

    target2 = tmp_path / "target-tampered"
    with pytest.raises(ValueError, match="Hash berkas tidak cocok"):
        restore_backup(tampered_archive, target2)
    assert not target2.exists() or not any(target2.iterdir())


def test_cleanup_keeps_linked_evidence(client: TestClient, owner_headers, business_id, app):
    settings: Settings = app.state.settings
    ev = client.post(
        f"/api/v1/businesses/{business_id}/files",
        headers=owner_headers,
        files={"file": ("linked.png", _png_bytes(), "image/png")},
    ).json()

    # Create an unreferenced orphan file and a stale .part file on disk
    evidence_root = settings.data_dir / "evidence"
    orphan_file = evidence_root / str(business_id) / "orphan-untracked.png"
    orphan_file.parent.mkdir(parents=True, exist_ok=True)
    orphan_file.write_bytes(_png_bytes())

    part_file = evidence_root / ".staging-orphan.part"
    part_file.write_bytes(b"partial")

    preview = preview_cleanup(settings)
    assert len(preview.orphan_paths) == 2
    assert preview.preview_token

    # Apply must fail when maintenance mode is off
    with pytest.raises(ValueError, match="Mode pemeliharaan wajib aktif"):
        apply_cleanup(settings, preview.preview_token)

    enable_maintenance(settings, reason="cleanup")
    try:
        with pytest.raises(ValueError, match="Token pratinjau tidak cocok"):
            apply_cleanup(settings, "invalid-token")

        removed = apply_cleanup(settings, preview.preview_token)
        assert removed.removed_count == 2
        assert not orphan_file.exists()
        assert not part_file.exists()

        # Tracked evidence file must remain untouched
        with Session(app.state.engine) as db:
            tracked = db.get(EvidenceFile, ev["id"])
            assert (evidence_root / tracked.storage_key).exists()
    finally:
        disable_maintenance(settings)


def test_demo_seed_labels_business(tmp_path, monkeypatch):
    monkeypatch.setenv("STOKGUARD_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    res = runner.invoke(
        cli,
        ["seed-demo", "--owner-username", "demo-owner", "--staff-username", "demo-staff"],
        input="demo-owner-pass-123\ndemo-owner-pass-123\ndemo-staff-pass-123\ndemo-staff-pass-123\n",
    )
    assert res.exit_code == 0, res.output
    assert "Data demonstrasi berhasil dibuat" in res.output

    engine = make_engine(tmp_path / "stokguard.db")
    try:
        with Session(engine) as db:
            biz = db.scalar(select(Business).where(Business.is_demo.is_(True)))
            assert biz is not None
            assert biz.is_demo is True
    finally:
        engine.dispose()
