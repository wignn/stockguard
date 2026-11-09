from uuid import uuid4

import pytest
from sqlalchemy import event, select
from sqlalchemy.orm import Session
from test_ledger import create_item, payload, post
from test_stocktakes import finalize, start


def cases_url(app):
    return f"/api/v1/businesses/{app.state.test_business_id}/cases"


def prepare_case(owner, staff, app):
    item = create_item(owner, app)
    assert post(owner, app, payload(app, item)).status_code == 201
    count = start(staff, app, item)
    result = finalize(staff, app, count, "18")
    assert result.status_code == 200
    case = owner.get(f"{cases_url(app)}/{result.json()['case_id']}").json()
    return item, count, case


def submit(client, app, case, count, **changes):
    return client.post(
        f"{cases_url(app)}/{case['id']}/submissions",
        json={
            "expected_case_version": case["version"],
            "stocktake_id": count["id"],
            "cause": "unrecorded_transaction",
            "resolution_kind": "movement",
            "quantity": "6",
            "movement_kind": "sale",
            "occurred_at": app.state.clock.now().isoformat(),
            "note": "Penjualan belum tercatat",
            "missing_evidence_reason": "Nota tidak ditemukan",
        }
        | changes,
    )


def decision(client, app, case, submission, value="approve", note="Ditinjau", key=None):
    return client.post(
        f"{cases_url(app)}/{case['id']}/decisions",
        json={
            "expected_case_version": submission["case_version"],
            "submission_id": submission["id"],
            "decision": value,
            "note": note,
        },
        headers={"Idempotency-Key": str(key or uuid4())},
    )


def test_submit_case_fixture_contract(submit_case, authenticated, staff, app):
    from uuid import UUID

    from stokguard.auth.dependencies import Actor, token_digest
    from stokguard.auth.models import AuthSession

    _, count, case = prepare_case(authenticated, staff, app)
    with Session(app.state.engine) as db:
        session = db.scalar(
            select(AuthSession).where(
                AuthSession.token_hash == token_digest(staff.cookies.get("stokguard_session"))
            )
        )
        actor = Actor(
            UUID(session.user_id), UUID(app.state.test_business_id), "staff", UUID(session.id)
        )
    result = submit_case(actor, case, count)
    assert result.case_id == case["id"]


def test_missed_sale_books_once_not_adjustment(authenticated, staff, app):
    item, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text
    key = uuid4()
    approved = decision(authenticated, app, case, submitted.json(), key=key)
    assert approved.status_code == 200, approved.text
    assert approved.json()["case_status"] == "resolved"
    assert decision(authenticated, app, case, submitted.json(), key=key).json() == approved.json()
    movements = authenticated.get(
        f"/api/v1/businesses/{app.state.test_business_id}/movements"
    ).json()
    assert movements["total"] == 2
    correction = next(m for m in movements["items"] if m["source_type"] == "case")
    assert correction["kind"] == "sale" and correction["quantity"] == "-6"
    assert correction["balance_quantity"] == "18"
    assert correction["source_id"] == case["id"]


def test_self_approval_forbidden(authenticated, staff, app):
    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(authenticated, app, case, count)
    assert submitted.status_code == 201, submitted.text
    assert decision(authenticated, app, case, submitted.json()).status_code == 403


def test_stale_submission_rejected(authenticated, staff, app):
    item, count, case = prepare_case(authenticated, staff, app)
    old = submit(staff, app, case, count)
    assert old.status_code == 201, old.text
    newer = start(staff, app, item)
    assert finalize(staff, app, newer, "19").status_code == 200
    current = authenticated.get(f"{cases_url(app)}/{case['id']}").json()
    new = submit(staff, app, current, newer, quantity="5")
    assert new.status_code == 201, new.text
    stale = old.json() | {"case_version": new.json()["case_version"]}
    assert decision(authenticated, app, case, stale).status_code == 409
    assert decision(authenticated, app, case, new.json()).status_code == 200


def test_recount_match_requires_review_without_movement(authenticated, staff, app):
    item, _, case = prepare_case(authenticated, staff, app)
    count = start(staff, app, item)
    assert finalize(staff, app, count, "24").status_code == 200
    case = authenticated.get(f"{cases_url(app)}/{case['id']}").json()
    assert case["status"] == "investigating"
    submitted = submit(
        staff,
        app,
        case,
        count,
        cause="miscount",
        resolution_kind="no_movement",
        quantity="0",
        movement_kind=None,
    )
    assert submitted.status_code == 201, submitted.text
    response = decision(authenticated, app, case, submitted.json())
    assert response.status_code == 200, response.text
    assert response.json()["movement_id"] is None
    assert (
        authenticated.get(f"/api/v1/businesses/{app.state.test_business_id}/movements").json()[
            "total"
        ]
        == 1
    )


def test_new_movement_requires_recount(authenticated, staff, app):
    item, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text
    assert post(authenticated, app, payload(app, item, "sale", "1", 1)).status_code == 201
    assert decision(authenticated, app, case, submitted.json()).status_code == 409
    updated = authenticated.get(f"{cases_url(app)}/{case['id']}").json()
    assert updated["status"] == "needs_recount"
    assert submit(staff, app, updated, count).status_code == 409


def test_reject_requires_note_preserves_balance(authenticated, staff, app):
    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text
    assert decision(authenticated, app, case, submitted.json(), "reject", " ").status_code == 422
    assert (
        decision(authenticated, app, case, submitted.json(), "reject", "Periksa nota").status_code
        == 200
    )
    updated = authenticated.get(f"{cases_url(app)}/{case['id']}").json()
    assert updated["status"] == "rejected"
    resubmitted = submit(staff, app, updated, count, note="Nota diperiksa, laporan staf terlampir")
    assert resubmitted.status_code == 201, resubmitted.text
    versions = authenticated.get(f"{cases_url(app)}/{case['id']}/submissions").json()
    assert versions["total"] == 2


def test_same_source_cannot_resolve_twice(authenticated, staff, app):
    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text
    assert decision(authenticated, app, case, submitted.json()).status_code == 200
    assert decision(authenticated, app, case, submitted.json()).status_code == 409


def test_approval_rollback_is_atomic(authenticated, staff, app):
    from stokguard.audit.models import AuditEvent
    from stokguard.inventory.models import StockBalance

    _, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text

    def fail(_mapper, _connection, target):
        if target.action == "case_decided":
            raise RuntimeError("Decision audit failure")

    event.listen(AuditEvent, "before_insert", fail)
    try:
        with pytest.raises(RuntimeError, match="Decision audit failure"):
            decision(authenticated, app, case, submitted.json())
    finally:
        event.remove(AuditEvent, "before_insert", fail)
    with Session(app.state.engine) as db:
        assert db.scalar(select(StockBalance.quantity_milli)) == 24000
    assert authenticated.get(f"{cases_url(app)}/{case['id']}").json()["status"] == "pending_review"


def test_active_recount_blocks_approval(authenticated, staff, app):
    item, count, case = prepare_case(authenticated, staff, app)
    submitted = submit(staff, app, case, count)
    assert submitted.status_code == 201, submitted.text
    start(staff, app, item)
    assert decision(authenticated, app, case, submitted.json()).status_code == 409


def test_unexplained_adjustment_requires_note_and_exact_quantity(authenticated, staff, app):
    _, count, case = prepare_case(authenticated, staff, app)
    assert submit(staff, app, case, count, quantity="5").status_code == 422
    assert (
        submit(
            staff,
            app,
            case,
            count,
            cause="unknown",
            resolution_kind="adjustment",
            movement_kind=None,
            missing_evidence_reason="",
        ).status_code
        == 422
    )
    submitted = submit(
        staff, app, case, count, cause="unknown", resolution_kind="adjustment", movement_kind=None
    )
    assert submitted.status_code == 201, submitted.text
    assert decision(authenticated, app, case, submitted.json()).status_code == 200
