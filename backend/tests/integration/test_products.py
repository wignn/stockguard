from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session


def product_payload(**changes):
    return {
        "sku": " kop-01 ",
        "name": "Kopi kemasan",
        "unit": "Pcs",
        "step_quantity": "1",
        "cost_rupiah": "1000",
    } | changes


def products_url(app, business_id=None):
    return f"/api/v1/businesses/{business_id or app.state.test_business_id}/products"


def test_product_starts_zero_without_movement(authenticated, app):
    response = authenticated.post(products_url(app), json=product_payload())
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["sku"] == "KOP-01"
    assert item["balance_quantity"] == "0"
    assert item["balance_version"] == 0
    assert item["version"] == 1
    assert item["cost_rupiah"] == "1000"
    from stokguard.inventory.models import StockMovement

    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0
    result = authenticated.get(products_url(app)).json()
    assert result["total"] == 1 and len(result["items"]) == 1
    balances = authenticated.get(products_url(app).replace("products", "balances"))
    assert balances.status_code == 200 and balances.json()["items"][0]["balance_quantity"] == "0"


def test_sku_normalization_unique_per_business(authenticated, app):
    assert authenticated.post(products_url(app), json=product_payload()).status_code == 201
    assert (
        authenticated.post(products_url(app), json=product_payload(sku="KOP-01")).status_code == 409
    )
    authenticated.cookies.clear()
    login = authenticated.post(
        "/api/v1/auth/login",
        json={"username": "owner-b", "password": "test-password-other", "mode": "web"},
    )
    authenticated.headers["X-CSRF-Token"] = login.json()["csrf_token"]
    assert (
        authenticated.post(
            products_url(app, app.state.other_business_id), json=product_payload()
        ).status_code
        == 201
    )


def test_staff_cannot_manage_catalog(client, app):
    from stokguard.auth.service import add_user
    from stokguard.core.transactions import write_uow

    with write_uow(app.state.engine) as db:
        add_user(
            db,
            app.state.test_business_id,
            "staff",
            "test-password-staff",
            "staff",
            app.state.clock.now(),
        )
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "staff", "password": "test-password-staff", "mode": "web"},
    )
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post(products_url(app), json=product_payload()).status_code == 403
    assert client.get(products_url(app)).status_code == 200


def test_unit_immutable_after_first_movement(authenticated, app):
    from stokguard.businesses.models import Location
    from stokguard.core.transactions import write_uow
    from stokguard.inventory.models import StockMovement

    item = authenticated.post(products_url(app), json=product_payload()).json()
    with write_uow(app.state.engine) as db:
        location = db.scalar(
            select(Location).where(Location.business_id == app.state.test_business_id)
        )
        db.add(
            StockMovement(
                business_id=app.state.test_business_id,
                product_id=item["id"],
                location_id=location.id,
                kind="incoming",
                quantity_milli=1000,
                cost_rupiah=1000,
                balance_after_milli=1000,
                balance_version=1,
                user_id=app.state.owner_id,
                occurred_at=app.state.clock.now().isoformat(),
                note="Test fixture",
            )
        )
    url = f"{products_url(app)}/{item['id']}"
    assert authenticated.patch(url, json={"expected_version": 1, "unit": "Kg"}).status_code == 409
    result = authenticated.patch(url, json={"expected_version": 1, "cost_rupiah": "2500"})
    assert result.status_code == 200, result.text
    assert result.json()["version"] == 2
    assert authenticated.patch(url, json={"expected_version": 1, "name": "Old"}).status_code == 409
    with Session(app.state.engine) as db:
        assert db.scalar(select(StockMovement.cost_rupiah)) == 1000

    import pytest

    with pytest.raises(ValueError, match="append-only"):
        with write_uow(app.state.engine) as db:
            movement = db.scalar(select(StockMovement))
            movement.cost_rupiah = 999
    with pytest.raises(ValueError, match="append-only"):
        with write_uow(app.state.engine) as db:
            db.delete(db.scalar(select(StockMovement)))


def test_foreign_product_hidden(authenticated, app):
    item = authenticated.post(products_url(app), json=product_payload()).json()
    foreign_url = f"{products_url(app, app.state.other_business_id)}/{item['id']}"
    assert authenticated.get(foreign_url).status_code == 404
    assert (
        authenticated.patch(foreign_url, json={"expected_version": 1, "active": False}).status_code
        == 404
    )


def test_invalid_product_amounts(authenticated, app):
    for value in ["0", "0.0001", "-1", "1e3", "NaN"]:
        assert (
            authenticated.post(
                products_url(app), json=product_payload(step_quantity=value)
            ).status_code
            == 422
        )
    for value in ["-1", "2.3", 1000]:
        assert (
            authenticated.post(
                products_url(app), json=product_payload(cost_rupiah=value)
            ).status_code
            == 422
        )
    assert (
        authenticated.post(
            products_url(app), json=product_payload(step_quantity="0.001", unit="Kg")
        ).status_code
        == 201
    )


def test_catalog_fixture_contract(make_product, app):
    from stokguard.auth.dependencies import Actor

    actor = Actor(UUID(app.state.owner_id), UUID(app.state.test_business_id), "owner", UUID(int=0))
    item = make_product(actor)
    assert item.sku == "TEST-01" and item.balance_quantity == "0"
