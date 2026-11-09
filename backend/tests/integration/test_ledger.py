from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session


def movement_url(app):
    return f"/api/v1/businesses/{app.state.test_business_id}/movements"


def create_item(client, app):
    response = client.post(
        f"/api/v1/businesses/{app.state.test_business_id}/products",
        json={
            "sku": "MOV-01",
            "name": "Produk transaksi",
            "unit": "Pcs",
            "step_quantity": "1",
            "cost_rupiah": "1000",
        },
    )
    assert response.status_code == 201
    return response.json()


def payload(app, product, kind="inbound", quantity="24", version=0):
    return {
        "product_id": product["id"],
        "kind": kind,
        "quantity": quantity,
        "occurred_at": app.state.clock.now().isoformat(),
        "note": "Pencatatan uji",
        "expected_balance_version": version,
    }


def post(client, app, command, key=None):
    return client.post(
        movement_url(app), json=command, headers={"Idempotency-Key": str(key or uuid4())}
    )


def test_book_fixture_contract(book, make_product, authenticated, app):
    from uuid import UUID

    from sqlalchemy import select

    from stokguard.auth.dependencies import Actor
    from stokguard.auth.models import AuthSession

    with Session(app.state.engine) as db:
        session_id = db.scalar(select(AuthSession.id))
    actor = Actor(
        UUID(app.state.owner_id), UUID(app.state.test_business_id), "owner", UUID(session_id)
    )
    product = make_product(actor)
    assert book(actor, product, "inbound", "3").balance_quantity == "3"


def test_direction_and_insufficient_stock(authenticated, app):
    item = create_item(authenticated, app)
    incoming = post(authenticated, app, payload(app, item))
    assert incoming.status_code == 201, incoming.text
    sale = post(authenticated, app, payload(app, item, "sale", "6", 1))
    assert sale.status_code == 201, sale.text
    assert sale.json()["balance_quantity"] == "18"
    assert sale.json()["quantity"] == "-6"
    assert post(authenticated, app, payload(app, item, "sale", "19", 2)).status_code == 409
    result = authenticated.get(movement_url(app)).json()
    assert result["total"] == 2
    assert authenticated.get(f"{movement_url(app)}/{sale.json()['id']}").status_code == 200
    timeline = authenticated.get(
        f"/api/v1/businesses/{app.state.test_business_id}/products/{item['id']}/timeline"
    )
    assert timeline.status_code == 200 and timeline.json()["total"] == 2
    events = authenticated.get(f"/api/v1/businesses/{app.state.test_business_id}/audit-events")
    assert events.status_code == 200
    assert len([e for e in events.json()["items"] if e["action"] == "movement_booked"]) == 2


def test_opening_once_per_product(authenticated, app):
    item = create_item(authenticated, app)
    assert post(authenticated, app, payload(app, item, "opening", "10")).status_code == 201
    assert post(authenticated, app, payload(app, item, "opening", "10", 1)).status_code == 409


def test_same_key_returns_same_result(authenticated, app):
    item = create_item(authenticated, app)
    key = uuid4()
    command = payload(app, item)
    first = post(authenticated, app, command, key)
    assert first.status_code == 201
    again = post(authenticated, app, command, key)
    assert again.status_code == 201
    assert again.json() == first.json()
    assert authenticated.get(movement_url(app)).json()["total"] == 1


def test_key_conflict(authenticated, app):
    item = create_item(authenticated, app)
    key = uuid4()
    assert post(authenticated, app, payload(app, item), key).status_code == 201
    assert post(authenticated, app, payload(app, item, quantity="25"), key).status_code == 409


def test_revoked_session_before_idempotency_replay(authenticated, app):
    item = create_item(authenticated, app)
    command, key = payload(app, item), uuid4()
    assert post(authenticated, app, command, key).status_code == 201
    assert authenticated.post("/api/v1/auth/logout").status_code == 200
    assert post(authenticated, app, command, key).status_code == 401


def test_atomic_rollback_when_audit_insert_fails(authenticated, app):
    from sqlalchemy import event

    from stokguard.audit.models import AuditEvent
    from stokguard.inventory.models import StockBalance, StockMovement

    item = create_item(authenticated, app)

    def fail_audit(_mapper, _connection, target):
        if target.action == "movement_booked":
            raise RuntimeError("Test audit failure")

    event.listen(AuditEvent, "before_insert", fail_audit)
    key = uuid4()
    try:
        with pytest.raises(RuntimeError, match="Test audit failure"):
            post(authenticated, app, payload(app, item), key)
    finally:
        event.remove(AuditEvent, "before_insert", fail_audit)
    with Session(app.state.engine) as db:
        assert db.scalar(select(StockBalance.quantity_milli)) == 0
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
    assert post(authenticated, app, payload(app, item), key).status_code == 201


def test_movement_validation_and_inactive_products(authenticated, app):
    item = create_item(authenticated, app)
    for value in ["0", "-1", "0.5", "1e3"]:
        assert post(authenticated, app, payload(app, item, quantity=value)).status_code == 422
    assert post(authenticated, app, payload(app, item) | {"source_type": "case"}).status_code == 422
    assert (
        post(
            authenticated, app, payload(app, item) | {"occurred_at": "2099-01-01T00:00:00Z"}
        ).status_code
        == 422
    )
    assert (
        post(
            authenticated, app, payload(app, item) | {"occurred_at": "2026-11-09T00:00:00"}
        ).status_code
        == 422
    )
    assert authenticated.post(movement_url(app), json=payload(app, item)).status_code == 422
    url = f"/api/v1/businesses/{app.state.test_business_id}/products/{item['id']}"
    assert (
        authenticated.patch(url, json={"expected_version": 1, "active": False}).status_code == 200
    )
    assert post(authenticated, app, payload(app, item)).status_code == 409
