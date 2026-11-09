from __future__ import annotations

from uuid import UUID, uuid4

from stokguard.auth.dependencies import Actor
from stokguard.auth.service import add_user, setup_business
from stokguard.core.clock import SystemClock
from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.maintenance import operation_slot
from stokguard.core.transactions import write_uow
from stokguard.inventory.ledger import book_movement
from stokguard.inventory.schemas import MovementCommand, MovementSource
from stokguard.products.schemas import ProductCreate
from stokguard.products.service import create_product
from stokguard.stocktakes.schemas import CountFinalize
from stokguard.stocktakes.service import finalize_stocktake, start_stocktake


def seed_demo(
    settings: Settings,
    *,
    owner_username: str,
    owner_password: str,
    staff_username: str,
    staff_password: str,
) -> UUID:
    with operation_slot(settings, "seed-demo"):
        now = SystemClock().now()
        engine = make_engine(settings.database_path)
        try:
            with write_uow(engine) as db:
                db.info["now"] = now
                business, owner = setup_business(
                    db,
                    "Toko Sembako Demo (Data Contoh)",
                    owner_username,
                    owner_password,
                    now,
                )
                business.is_demo = True
                staff = add_user(
                    db,
                    UUID(business.id),
                    staff_username,
                    staff_password,
                    "staff",
                    now,
                )
                owner_actor = Actor(
                    user_id=UUID(owner.id),
                    business_id=UUID(business.id),
                    role="owner",
                    session_id=uuid4(),
                )
                staff_actor = Actor(
                    user_id=UUID(staff.id),
                    business_id=UUID(business.id),
                    role="staff",
                    session_id=uuid4(),
                )

                beras = create_product(
                    db,
                    owner_actor,
                    ProductCreate(
                        sku="DEMO-BRS-5KG",
                        name="Beras Pandan Wangi 5kg",
                        unit="pack",
                        step_quantity="1",
                        cost_rupiah="68000",
                    ),
                )
                minyak = create_product(
                    db,
                    owner_actor,
                    ProductCreate(
                        sku="DEMO-MNY-1L",
                        name="Minyak Goreng Kemasan 1L",
                        unit="pcs",
                        step_quantity="1",
                        cost_rupiah="17500",
                    ),
                )

                book_movement(
                    db,
                    owner_actor,
                    MovementCommand(
                        product_id=UUID(beras.id),
                        kind="opening",
                        quantity="25",
                        occurred_at=now,
                        note="Stok awal demonstrasi beras",
                        expected_balance_version=0,
                    ),
                    source=MovementSource(kind="manual"),
                )
                book_movement(
                    db,
                    staff_actor,
                    MovementCommand(
                        product_id=UUID(beras.id),
                        kind="sale",
                        quantity="3",
                        occurred_at=now,
                        note="Penjualan harian demonstrasi",
                        expected_balance_version=1,
                    ),
                    source=MovementSource(kind="manual"),
                )
                book_movement(
                    db,
                    owner_actor,
                    MovementCommand(
                        product_id=UUID(minyak.id),
                        kind="opening",
                        quantity="40",
                        occurred_at=now,
                        note="Stok awal demonstrasi minyak",
                        expected_balance_version=0,
                    ),
                    source=MovementSource(kind="manual"),
                )

                count = start_stocktake(db, staff_actor, UUID(beras.id))
                finalize_stocktake(
                    db,
                    staff_actor,
                    UUID(count.id),
                    CountFinalize(
                        counted_quantity="20",
                        expected_version=count.version,
                        no_physical_movement=True,
                        recounted=True,
                        rack_checked=True,
                        storage_checked=True,
                    ),
                )
                return UUID(business.id)
        finally:
            engine.dispose()
