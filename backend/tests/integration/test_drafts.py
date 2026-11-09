from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_files import upload


def base(app):
    return f"/api/v1/businesses/{app.state.test_business_id}"


def draft_url(app):
    return base(app) + "/transaction-drafts"


def create_draft(client, app, **changes):
    file = upload(client, app).json()
    payload = {
        "file_id": file["id"],
        "receipt_number": "SYN-001",
        "lines": [{"quantity": "2"}, {"quantity": "3"}],
        **changes,
    }
    response = client.post(draft_url(app), json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def product(client, app):
    response = client.post(
        base(app) + "/products",
        json={
            "sku": "DRAFT-01",
            "name": "Roti",
            "unit": "Pcs",
            "step_quantity": "1",
            "cost_rupiah": "1000",
        },
    )
    assert response.status_code == 201
    return response.json()


def line_url(app, draft, line=None):
    return draft_url(app) + f"/{draft['id']}/lines/{(line or draft['lines'][0])['id']}"


def match_line(client, app, draft, item):
    response = client.patch(
        line_url(app, draft),
        json={
            "expected_version": draft["lines"][0]["version"],
            "product_id": item["id"],
            "kind": "inbound",
            "quantity": "2",
            "unit_price_rupiah": "1500",
            "occurred_at": app.state.clock.now().isoformat(),
            "note": "Sudah diperiksa",
        },
    )
    assert response.status_code == 200, response.text
    return response.json()


def confirm(client, app, draft, line=None, key=None, **changes):
    payload = {
        "expected_line_version": (line or draft["lines"][0])["version"],
        "expected_balance_version": 0,
        "reviewed": True,
        **changes,
    }
    return client.post(
        line_url(app, draft) + "/confirm",
        json=payload,
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def test_unreviewed_or_unmatched_product_cannot_confirm(authenticated, app):
    draft = create_draft(authenticated, app)
    assert confirm(authenticated, app, draft).status_code == 422
    line = match_line(authenticated, app, draft, product(authenticated, app))
    assert confirm(authenticated, app, draft, line, reviewed=False).status_code == 422
    foreign = authenticated.get(
        f"/api/v1/businesses/{app.state.other_business_id}/transaction-drafts/{draft['id']}"
    )
    assert foreign.status_code == 404


def test_partial_patch_preserves_other_reviewed_fields(authenticated, app):
    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, product(authenticated, app))
    changed = authenticated.patch(
        line_url(app, draft), json={"expected_version": line["version"], "quantity": "4"}
    )
    assert changed.status_code == 200, changed.text
    assert changed.json()["note"] == line["note"] and changed.json()["quantity"] == "4"


def test_same_line_new_keys_books_once(authenticated, app):
    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, product(authenticated, app))
    key = uuid4()
    first = confirm(authenticated, app, draft, line, key)
    assert first.status_code == 201, first.text
    replay = confirm(authenticated, app, draft, line, key)
    assert replay.status_code == 201 and replay.json() == first.json()
    assert confirm(authenticated, app, draft, line).status_code == 409
    changed = confirm(authenticated, app, draft, line, key, expected_balance_version=1)
    assert changed.status_code == 409
    from stokguard.files.models import EvidenceLink
    from stokguard.inventory.models import StockMovement

    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 1
        link = db.scalar(select(EvidenceLink).where(EvidenceLink.target_type == "movement"))
        assert link.file_id == draft["file_id"] and link.movement_id == first.json()["id"]


def test_partial_lines_remain_visible(authenticated, app):
    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, product(authenticated, app))
    assert confirm(authenticated, app, draft, line).status_code == 201
    detail = authenticated.get(draft_url(app) + f"/{draft['id']}").json()
    assert detail["status"] == "partial"
    assert [line["status"] for line in detail["lines"]] == ["confirmed", "pending"]
    assert authenticated.get(draft_url(app)).json()["total"] == 1


def test_edit_confirmed_line_rejected(authenticated, app):
    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, product(authenticated, app))
    assert confirm(authenticated, app, draft, line).status_code == 201
    assert (
        authenticated.patch(
            line_url(app, draft), json={"expected_version": line["version"] + 1, "quantity": "8"}
        ).status_code
        == 409
    )


def test_duplicate_receipt_number_warns_in_business_only(authenticated, app):
    first = create_draft(authenticated, app)
    second = create_draft(authenticated, app)
    assert second["duplicate_ids"] == [first["id"]]
    changed = authenticated.patch(
        draft_url(app) + f"/{second['id']}",
        json={"expected_version": second["version"], "receipt_number": "SYN-002"},
    )
    assert changed.status_code == 200 and changed.json()["duplicate_ids"] == []
    assert (
        authenticated.get(
            f"/api/v1/businesses/{app.state.other_business_id}/transaction-drafts"
        ).status_code
        == 404
    )


def test_manual_entry_after_ocr_failure(authenticated, app):
    from stokguard.ocr.engine import TesseractEngine
    from stokguard.ocr.worker import process_one

    file = upload(authenticated, app).json()
    job = authenticated.post(base(app) + "/ocr-jobs", json={"file_id": file["id"]}).json()
    process_one(
        app.state.settings,
        TesseractEngine("not-installed-tesseract", "eng"),
        now=app.state.clock.now(),
    )
    assert authenticated.get(base(app) + f"/ocr-jobs/{job['id']}").json()["status"] == "failed"
    draft = create_draft(authenticated, app, file_id=file["id"])
    line = match_line(authenticated, app, draft, product(authenticated, app))
    assert confirm(authenticated, app, draft, line).status_code == 201


def test_ocr_completion_creates_unmatched_suggestions_only(authenticated, app):
    from stokguard.ocr.engine import OcrText
    from stokguard.ocr.worker import process_one

    file = upload(authenticated, app).json()
    job = authenticated.post(base(app) + "/ocr-jobs", json={"file_id": file["id"]}).json()

    class Engine:
        def recognize(self, path, timeout_seconds):
            return OcrText(
                "SYNTHETIC FIXTURE\nNo Nota: SYN-OCR\nRoti|2|1000\n<script>text</script>"
            )

    process_one(app.state.settings, Engine(), now=app.state.clock.now())
    drafts = authenticated.get(draft_url(app)).json()["items"]
    assert len(drafts) == 1 and drafts[0]["ocr_job_id"] == job["id"]
    draft = authenticated.get(draft_url(app) + f"/{drafts[0]['id']}").json()
    assert "<script>text</script>" in draft["original_ocr"]["raw_text"]
    assert draft["lines"][0]["suggestion"]["quantity"] == "2"
    assert draft["lines"][0]["product_id"] is None and draft["lines"][0]["quantity"] is None
    assert confirm(authenticated, app, draft).status_code == 422


def test_active_stocktake_preserves_pending_line(authenticated, app):
    draft = create_draft(authenticated, app)
    item = product(authenticated, app)
    line = match_line(authenticated, app, draft, item)
    assert (
        authenticated.post(base(app) + "/stocktakes", json={"product_id": item["id"]}).status_code
        == 201
    )
    assert confirm(authenticated, app, draft, line).status_code == 409
    detail = authenticated.get(draft_url(app) + f"/{draft['id']}").json()
    assert detail["lines"][0]["status"] == "pending"


def test_concurrent_confirmation_books_once(authenticated, app):
    from stokguard.auth.dependencies import Actor
    from stokguard.auth.models import AuthSession
    from stokguard.core.errors import DomainError
    from stokguard.drafts.schemas import DraftConfirm
    from stokguard.drafts.service import confirm_draft_line

    draft = create_draft(authenticated, app)
    line = match_line(authenticated, app, draft, product(authenticated, app))
    with Session(app.state.engine) as db:
        session = db.scalar(select(AuthSession).where(AuthSession.user_id == app.state.owner_id))
        actor = Actor(
            user_id=app.state.owner_id,
            business_id=app.state.test_business_id,
            session_id=session.id,
            role="owner",
        )
    barrier = Barrier(2)

    def work():
        barrier.wait()
        try:
            confirm_draft_line(
                app.state.engine,
                actor,
                draft["id"],
                line["id"],
                DraftConfirm(
                    expected_line_version=line["version"], expected_balance_version=0, reviewed=True
                ),
                uuid4(),
                now=app.state.clock.now(),
            )
            return 201
        except DomainError as exc:
            return exc.status

    with ThreadPoolExecutor(2) as pool:
        assert sorted(pool.map(lambda _: work(), range(2))) == [201, 409]
