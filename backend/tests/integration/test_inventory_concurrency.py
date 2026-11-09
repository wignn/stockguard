from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session
from test_ledger import create_item, movement_url, payload, post


def test_two_sales_cannot_oversell(authenticated, app):
    item = create_item(authenticated, app)
    assert post(authenticated, app, payload(app, item, quantity="10")).status_code == 201
    barrier = Barrier(2)
    cookies = dict(authenticated.cookies)
    headers = dict(authenticated.headers)

    def sale():
        with TestClient(app, cookies=cookies, headers=headers) as client:
            barrier.wait(timeout=10)
            return post(client, app, payload(app, item, "sale", "7", 1)).status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: sale(), range(2)))
    assert sorted(results) == [201, 409]
    from stokguard.inventory.models import StockBalance

    with Session(app.state.engine) as db:
        assert db.scalar(select(StockBalance.quantity_milli)) == 3000
        assert db.scalar(select(StockBalance.version)) == 2


def test_lock_timeout_is_retryable_without_partial_write(authenticated, app):
    item = create_item(authenticated, app)
    key = uuid4()
    with app.state.engine.connect() as lock:
        lock.exec_driver_sql("BEGIN IMMEDIATE")
        response = post(authenticated, app, payload(app, item), key)
        assert response.status_code == 503
        assert response.json()["error"]["code"] == "database_busy"
        lock.rollback()
    assert post(authenticated, app, payload(app, item), key).status_code == 201
    assert authenticated.get(movement_url(app)).json()["total"] == 1
