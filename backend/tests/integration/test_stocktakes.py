from datetime import timedelta

import pytest
from test_ledger import create_item, payload, post


def test_count_fixture_contract(start_count, finish_count, make_product, authenticated, app):
    from uuid import UUID

    from sqlalchemy import select
    from sqlalchemy.orm import Session

    from stokguard.auth.dependencies import Actor
    from stokguard.auth.models import AuthSession

    with Session(app.state.engine) as db:
        session_id = db.scalar(select(AuthSession.id))
    actor = Actor(
        UUID(app.state.owner_id), UUID(app.state.test_business_id), "owner", UUID(session_id)
    )
    item = make_product(actor)
    count = start_count(actor, item)
    assert finish_count(actor, count, "0").difference_quantity == "0"


def count_url(app):
    return f"/api/v1/businesses/{app.state.test_business_id}/stocktakes"


def start(client, app, item):
    result = client.post(count_url(app), json={"product_id": item["id"]})
    assert result.status_code == 201, result.text
    return result.json()


def finalize(client, app, count, quantity, **changes):
    return client.post(
        f"{count_url(app)}/{count['id']}/finalize",
        json={
            "counted_quantity": quantity,
            "expected_version": count["version"],
            "recounted": True,
            "rack_checked": True,
            "storage_checked": True,
            "no_physical_movement": True,
        }
        | changes,
    )


def stocked(authenticated, app):
    item = create_item(authenticated, app)
    assert post(authenticated, app, payload(app, item)).status_code == 201
    return item


def test_matching_count_closes_without_case(authenticated, app):
    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    assert count["baseline_quantity"] == "24"
    result = finalize(authenticated, app, count, "24")
    assert result.status_code == 200, result.text
    assert result.json()["difference_quantity"] == "0"
    assert result.json()["case_id"] is None
    assert "100%" not in result.text
    assert authenticated.get(count_url(app)).json()["total"] == 1
    assert authenticated.get(f"{count_url(app)}/{count['id']}").json()["status"] == "finalized"


@pytest.mark.parametrize(("quantity", "difference"), [("18", "-6"), ("30", "6")])
def test_shortage_and_surplus(authenticated, app, quantity, difference):
    item = stocked(authenticated, app)
    result = finalize(authenticated, app, start(authenticated, app, item), quantity)
    assert result.status_code == 200, result.text
    assert result.json()["difference_quantity"] == difference
    case_id = result.json()["case_id"]
    assert case_id
    case = authenticated.get(count_url(app).replace("stocktakes", "cases") + f"/{case_id}").json()
    assert case["difference_quantity"] == difference
    assert case["status"] == "investigating"
    # A count never writes an inventory correction.
    products = authenticated.get(
        f"/api/v1/businesses/{app.state.test_business_id}/products/{item['id']}"
    ).json()
    assert products["balance_quantity"] == "24"


def test_zero_baseline_no_percentage(authenticated, app):
    item = create_item(authenticated, app)
    result = finalize(authenticated, app, start(authenticated, app, item), "2")
    assert result.status_code == 200, result.text
    assert result.json()["difference_percentage"] is None


def test_confirmations_required_for_difference(authenticated, app):
    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    assert finalize(authenticated, app, count, "18", recounted=False).status_code == 422
    assert finalize(authenticated, app, count, "24", no_physical_movement=False).status_code == 422
    assert finalize(authenticated, app, count, "18").status_code == 200
    assert finalize(authenticated, app, count, "18").status_code == 409


def test_only_one_active_count(authenticated, app):
    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    assert authenticated.post(count_url(app), json={"product_id": item["id"]}).status_code == 409
    response = authenticated.post(
        f"{count_url(app)}/{count['id']}/cancel",
        json={"expected_version": count["version"], "note": "Hitung dibatalkan"},
    )
    assert response.status_code == 200, response.text
    assert start(authenticated, app, item)["id"] != count["id"]


def test_expired_session_cannot_finalize(authenticated, app):
    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    app.state.clock.value += timedelta(minutes=15)
    result = finalize(authenticated, app, count, "24")
    assert result.status_code == 409
    assert start(authenticated, app, item)["id"] != count["id"]


def test_movement_blocked_during_count(authenticated, app):
    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    result = post(authenticated, app, payload(app, item, "sale", "1", 1))
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "active_stocktake"
    assert finalize(authenticated, app, count, "24").status_code == 200
    assert post(authenticated, app, payload(app, item, "sale", "1", 1)).status_code == 201


def test_recount_attaches_existing_case(authenticated, app):
    item = stocked(authenticated, app)
    first = start(authenticated, app, item)
    result = finalize(authenticated, app, first, "18").json()
    second = start(authenticated, app, item)
    recount = finalize(authenticated, app, second, "24")
    assert recount.status_code == 200, recount.text
    assert recount.json()["case_id"] == result["case_id"]
    url = count_url(app).replace("stocktakes", "cases") + f"/{result['case_id']}"
    case = authenticated.get(url).json()
    assert case["initial_stocktake_id"] == first["id"]
    assert case["latest_stocktake_id"] == second["id"]
    assert case["status"] != "closed"
    updated = authenticated.patch(
        url + "/findings",
        json={"expected_version": case["version"], "note": "Barang ditemukan di rak kedua."},
    )
    assert updated.status_code == 200, updated.text


def test_count_holder_and_extend(authenticated, app):
    from stokguard.auth.service import add_user
    from stokguard.core.transactions import write_uow

    item = stocked(authenticated, app)
    count = start(authenticated, app, item)
    extended = authenticated.post(
        f"{count_url(app)}/{count['id']}/extend",
        json={"expected_version": count["version"], "note": "Periksa gudang"},
    )
    assert extended.status_code == 200, extended.text
    with write_uow(app.state.engine) as db:
        add_user(
            db,
            app.state.test_business_id,
            "count-staff",
            "test-password-staff",
            "staff",
            app.state.clock.now(),
        )
    authenticated.cookies.clear()
    logged = authenticated.post(
        "/api/v1/auth/login",
        json={"username": "count-staff", "password": "test-password-staff", "mode": "web"},
    )
    authenticated.headers["X-CSRF-Token"] = logged.json()["csrf_token"]
    assert finalize(authenticated, app, extended.json(), "24").status_code == 403


def test_count_and_sale_race_has_consistent_snapshot(authenticated, app):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier

    from fastapi.testclient import TestClient

    item = stocked(authenticated, app)
    barrier = Barrier(2)
    cookies, headers = dict(authenticated.cookies), dict(authenticated.headers)

    def operation(kind):
        with TestClient(app, cookies=cookies, headers=headers) as client:
            barrier.wait(timeout=10)
            if kind == "count":
                return client.post(count_url(app), json={"product_id": item["id"]})
            return post(client, app, payload(app, item, "sale", "6", 1))

    with ThreadPoolExecutor(max_workers=2) as executor:
        count_future = executor.submit(operation, "count")
        sale_future = executor.submit(operation, "sale")
        count, sale = count_future.result(), sale_future.result()
    assert count.status_code == 201
    if sale.status_code == 201:
        assert count.json()["baseline_quantity"] == "18"
        assert count.json()["baseline_version"] == 2
    else:
        assert sale.status_code == 409
        assert count.json()["baseline_quantity"] == "24"
        assert count.json()["baseline_version"] == 1
