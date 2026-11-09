from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from stokguard.core.config import Settings
from stokguard.main import create_app


class FrozenClock:
    def __init__(self):
        self.value = datetime(2026, 11, 9, 8, tzinfo=UTC)

    def now(self):
        return self.value


@pytest.fixture
def app(tmp_path):
    from stokguard.auth.service import setup_business
    from stokguard.core.db import Base
    from stokguard.core.transactions import write_uow

    application = create_app(Settings(data_dir=tmp_path))
    application.state.clock = FrozenClock()
    Base.metadata.create_all(application.state.engine)
    with write_uow(application.state.engine) as db:
        business, owner = setup_business(
            db, "Test business A", "owner-a", "test-password-owner", application.state.clock.now()
        )
        other_business, _ = setup_business(
            db, "Test business B", "owner-b", "test-password-other", application.state.clock.now()
        )
    application.state.test_business_id = business.id
    application.state.other_business_id = other_business.id
    application.state.owner_id = owner.id
    yield application
    application.state.engine.dispose()


@pytest.fixture
def client(app):
    with TestClient(app) as test_client:
        test_client.headers["Origin"] = "http://localhost:3000"
        yield test_client


@pytest.fixture
def authenticated(client):
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "owner-a", "password": "test-password-owner", "mode": "web"},
    )
    assert response.status_code == 200, response.text
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    return client


@pytest.fixture
def make_product(app):
    from stokguard.core.transactions import write_uow
    from stokguard.products.schemas import ProductCreate
    from stokguard.products.service import create_product

    def make(actor, *, sku="TEST-01", cost="1000", step="1"):
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            return create_product(
                db,
                actor,
                ProductCreate(
                    sku=sku, name="Produk uji", unit="Pcs", step_quantity=step, cost_rupiah=cost
                ),
            )

    return make


@pytest.fixture
def book(app):
    from uuid import uuid4

    from sqlalchemy import select

    from stokguard.core.transactions import write_uow
    from stokguard.inventory.ledger import post_in_session
    from stokguard.inventory.models import StockBalance
    from stokguard.inventory.schemas import MovementCommand

    def record(actor, product, kind, quantity, *, key=None, expected_version=None):
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            balance = db.scalar(
                select(StockBalance).where(
                    StockBalance.business_id == str(actor.business_id),
                    StockBalance.product_id == product.id,
                )
            )
            command = MovementCommand(
                product_id=product.id,
                kind=kind,
                quantity=quantity,
                occurred_at=app.state.clock.now(),
                note="Test fixture",
                expected_balance_version=balance.version
                if expected_version is None
                else expected_version,
            )
            return post_in_session(db, actor, command, key or uuid4())

    return record


@pytest.fixture
def start_count(app):
    from uuid import UUID

    from stokguard.core.transactions import write_uow
    from stokguard.stocktakes.service import start_stocktake

    def start(actor, product):
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            return start_stocktake(db, actor, UUID(product.id))

    return start


@pytest.fixture
def finish_count(app):
    from uuid import UUID

    from stokguard.core.transactions import write_uow
    from stokguard.stocktakes.schemas import CountFinalize
    from stokguard.stocktakes.service import finalize_stocktake

    def finish(actor, count, quantity, *, confirmed=True):
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            return finalize_stocktake(
                db,
                actor,
                UUID(count.id),
                CountFinalize(
                    counted_quantity=quantity,
                    expected_version=count.version,
                    recounted=confirmed,
                    rack_checked=confirmed,
                    storage_checked=confirmed,
                    no_physical_movement=confirmed,
                ),
            )

    return finish


@pytest.fixture
def submit_case(app):
    from uuid import UUID

    from stokguard.approvals.schemas import SubmissionCreate
    from stokguard.approvals.service import submit_case as submit
    from stokguard.core.transactions import write_uow

    def record(actor, case, count, **changes):
        command = SubmissionCreate(
            **(
                {
                    "expected_case_version": case["version"],
                    "stocktake_id": count["id"],
                    "cause": "unrecorded_transaction",
                    "resolution_kind": "movement",
                    "quantity": "6",
                    "movement_kind": "sale",
                    "occurred_at": app.state.clock.now(),
                    "note": "Penjualan terlewat",
                    "missing_evidence_reason": "Nota tidak ditemukan",
                }
                | changes
            )
        )
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            return submit(db, actor, UUID(case["id"]), command)

    return record


@pytest.fixture
def staff(app):
    from stokguard.auth.service import add_user
    from stokguard.core.transactions import write_uow

    with write_uow(app.state.engine) as db:
        add_user(
            db,
            app.state.test_business_id,
            "review-staff",
            "test-password-staff",
            "staff",
            app.state.clock.now(),
        )
    with TestClient(app, headers={"Origin": "http://localhost:3000"}) as client:
        response = client.post(
            "/api/v1/auth/login",
            json={"username": "review-staff", "password": "test-password-staff", "mode": "web"},
        )
        client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        yield client
