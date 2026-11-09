from datetime import timedelta
from multiprocessing import get_context
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session
from test_files import upload


def jobs_url(app):
    return f"/api/v1/businesses/{app.state.test_business_id}/ocr-jobs"


def enqueue(client, app):
    item = upload(client, app).json()
    response = client.post(jobs_url(app), json={"file_id": item["id"]})
    assert response.status_code == 201, response.text
    return response.json()


def test_timeout_and_missing_executable_visible(authenticated, app):
    import pytest

    from stokguard.ocr.engine import OcrFailure, TesseractEngine
    from stokguard.ocr.worker import process_one

    job = enqueue(authenticated, app)
    process_one(
        app.state.settings,
        TesseractEngine("definitely-not-installed-tesseract", "eng"),
        now=app.state.clock.now(),
    )
    detail = authenticated.get(jobs_url(app) + f"/{job['id']}").json()
    assert detail["status"] == "failed" and detail["error_code"] == "ocr_unavailable"
    with pytest.raises(OcrFailure) as failure:
        TesseractEngine("definitely-not-installed-tesseract", "eng").recognize(Path("unused"), 60)
    assert failure.value.code == "ocr_unavailable"

    class TimeoutEngine:
        def recognize(self, image_path, timeout_seconds):
            assert timeout_seconds == 60
            raise OcrFailure("ocr_timeout")

    retried = authenticated.post(jobs_url(app) + f"/{job['id']}/retry")
    assert retried.status_code == 201
    assert retried.json()["id"] != job["id"]
    process_one(app.state.settings, TimeoutEngine(), now=app.state.clock.now())
    assert (
        authenticated.get(jobs_url(app) + f"/{retried.json()['id']}").json()["error_code"]
        == "ocr_timeout"
    )
    assert (
        authenticated.get(jobs_url(app) + f"/{job['id']}").json()["error_code"] == "ocr_unavailable"
    )


def test_expired_lease_retries_once(authenticated, app):
    from stokguard.core.transactions import write_uow
    from stokguard.ocr.jobs import claim_job
    from stokguard.ocr.models import OcrJob

    item = enqueue(authenticated, app)
    now = app.state.clock.now()
    with write_uow(app.state.engine) as db:
        first = claim_job(db, now)
    assert first.expires_at == now + timedelta(seconds=120)
    with write_uow(app.state.engine) as db:
        assert claim_job(db, now + timedelta(seconds=119)) is None
    with write_uow(app.state.engine) as db:
        second = claim_job(db, first.expires_at)
    assert second.job_id == first.job_id and second.fencing_token != first.fencing_token
    with write_uow(app.state.engine) as db:
        assert claim_job(db, second.expires_at) is None
    with Session(app.state.engine) as db:
        job = db.get(OcrJob, item["id"])
        assert job.attempts == 2 and job.status == "failed" and job.error_code == "lease_expired"


def test_stale_worker_cannot_overwrite_new_result(authenticated, app):
    from stokguard.core.transactions import write_uow
    from stokguard.ocr.jobs import claim_job, complete_job, fail_job
    from stokguard.ocr.parser import parse_receipt

    item = enqueue(authenticated, app)
    now = app.state.clock.now()
    with write_uow(app.state.engine) as db:
        old = claim_job(db, now)
    with write_uow(app.state.engine) as db:
        current = claim_job(db, old.expires_at)
        db.info["now"] = old.expires_at
        assert complete_job(db, current, parse_receipt("new result"))
    with write_uow(app.state.engine) as db:
        db.info["now"] = old.expires_at
        assert not complete_job(db, old, parse_receipt("stale result"))
        assert not fail_job(db, old, "stale_error")
    detail = authenticated.get(jobs_url(app) + f"/{item['id']}").json()
    assert detail["result"]["raw_text"] == "new result" and detail["status"] == "succeeded"


def blocked_worker(settings, now, started, release):
    from stokguard.ocr.engine import OcrText
    from stokguard.ocr.worker import process_one

    class BlockedEngine:
        def recognize(self, image_path, timeout_seconds):
            assert image_path.is_file()
            started.set()
            assert release.wait(15)
            return OcrText("SYNTHETIC OCR FIXTURE\nRoti|2|1000")

    process_one(settings, BlockedEngine(), now=now)


def test_api_ledger_remains_usable_while_ocr_runs(authenticated, app):
    item = enqueue(authenticated, app)
    context = get_context("spawn")
    started, release = context.Event(), context.Event()
    process = context.Process(
        target=blocked_worker,
        args=(
            app.state.settings,
            app.state.clock.now(),
            started,
            release,
        ),
    )
    process.start()
    try:
        assert started.wait(10)
        base = f"/api/v1/businesses/{app.state.test_business_id}"
        product = authenticated.post(
            base + "/products",
            json={
                "sku": "OCR-CONCURRENT",
                "name": "Roti",
                "unit": "Pcs",
                "step_quantity": "1",
                "cost_rupiah": "1000",
            },
        )
        assert product.status_code == 201
        from uuid import uuid4

        movement = authenticated.post(
            base + "/movements",
            headers={"Idempotency-Key": str(uuid4())},
            json={
                "product_id": product.json()["id"],
                "kind": "opening",
                "quantity": "10",
                "expected_balance_version": 0,
                "occurred_at": app.state.clock.now().isoformat(),
                "note": "Stok awal",
            },
        )
        assert movement.status_code == 201, movement.text
    finally:
        release.set()
        process.join(15)
        if process.is_alive():
            process.terminate()
            process.join(5)
    assert process.exitcode == 0
    detail = authenticated.get(jobs_url(app) + f"/{item['id']}").json()
    assert detail["status"] == "succeeded"
    with Session(app.state.engine) as db:
        from stokguard.inventory.models import StockMovement

        assert len(db.scalars(select(StockMovement)).all()) == 1


def test_cli_ocr_commands_report_local_availability(monkeypatch):
    from typer.testing import CliRunner

    from stokguard.cli import cli
    from stokguard.ocr.engine import TesseractEngine

    monkeypatch.setattr(TesseractEngine, "available", lambda self: False)
    result = CliRunner().invoke(cli, ["ocr-check"])
    assert result.exit_code == 1 and "unavailable" in result.output
    help_result = CliRunner().invoke(cli, ["worker", "--help"])
    assert help_result.exit_code == 0


def test_ocr_job_tenant_scope_and_retry_state(authenticated, app):
    item = enqueue(authenticated, app)
    assert authenticated.post(jobs_url(app) + f"/{item['id']}/retry").status_code == 409
    foreign = f"/api/v1/businesses/{app.state.other_business_id}/ocr-jobs"
    assert authenticated.get(foreign + f"/{item['id']}").status_code == 404
    assert authenticated.post(foreign, json={"file_id": item["file_id"]}).status_code == 404
