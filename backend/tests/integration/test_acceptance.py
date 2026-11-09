from datetime import timedelta

from fastapi.testclient import TestClient
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_approvals import decision, prepare_case, submit
from test_drafts import base, confirm, create_draft, draft_url, match_line, product
from test_files import upload

from stokguard.core.transactions import write_uow
from stokguard.drafts.models import TransactionDraft
from stokguard.inventory.models import StockBalance, StockMovement
from stokguard.ocr.engine import OcrText
from stokguard.ocr.jobs import claim_job, complete_job
from stokguard.ocr.parser import parse_receipt
from stokguard.ocr.worker import process_one


def test_foreign_file_cannot_create_draft_or_leak_content(authenticated, app):
    file = upload(authenticated, app).json()
    with TestClient(app, headers={"Origin": "http://localhost:3000"}) as other:
        login = other.post(
            "/api/v1/auth/login",
            json={"username": "owner-b", "password": "test-password-other", "mode": "web"},
        )
        assert login.status_code == 200
        other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        root = f"/api/v1/businesses/{app.state.other_business_id}"
        response = other.post(
            root + "/transaction-drafts", json={"file_id": file["id"], "lines": [{}]}
        )
        assert response.status_code == 404
        assert other.get(root + f"/files/{file['id']}/content").status_code == 404
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(TransactionDraft)) == 0
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_product_archived_after_review_cannot_book_partial_draft(authenticated, app):
    item = product(authenticated, app)
    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, item)
    archived = authenticated.patch(
        base(app) + f"/products/{item['id']}",
        json={"expected_version": item["version"], "active": False},
    )
    assert archived.status_code == 200, archived.text
    response = confirm(authenticated, app, draft, line)
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "product_inactive"
    detail = authenticated.get(draft_url(app) + f"/{draft['id']}").json()
    assert detail["lines"][0]["status"] == "pending"
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
        assert db.scalar(select(StockBalance.quantity_milli)) == 0


def test_duplicate_submission_and_decision_never_duplicate_stock(authenticated, staff, app):
    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201
    assert submit(staff, app, case, count).status_code == 409
    approved = decision(authenticated, app, case, submitted.json())
    assert approved.status_code == 200
    assert decision(authenticated, app, case, submitted.json()).status_code == 409
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 2
        assert db.scalar(select(StockBalance.quantity_milli)) == 18_000


def test_restarted_worker_recovers_expired_job_without_accepting_old_result(authenticated, app):
    file = upload(authenticated, app).json()
    response = authenticated.post(base(app) + "/ocr-jobs", json={"file_id": file["id"]})
    assert response.status_code == 201
    now = app.state.clock.now()
    with write_uow(app.state.engine) as db:
        old_lease = claim_job(db, now)
    assert old_lease is not None

    class Engine:
        def recognize(self, image_path, timeout_seconds):
            return OcrText("No Nota: RESTART-01\nBeras|2|1000")

    later = now + timedelta(seconds=121)
    assert process_one(app.state.settings, Engine(), now=later)
    with write_uow(app.state.engine) as db:
        db.info["now"] = later
        complete_job(db, old_lease, parse_receipt("No Nota: STALE\nBeras|99|1000"))
    detail = authenticated.get(base(app) + f"/ocr-jobs/{response.json()['id']}").json()
    assert detail["status"] == "succeeded"
    with Session(app.state.engine) as db:
        drafts = db.scalars(select(TransactionDraft)).all()
        assert len(drafts) == 1
        assert drafts[0].receipt_number == "RESTART-01"
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
