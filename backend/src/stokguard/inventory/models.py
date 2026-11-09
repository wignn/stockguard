from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    UniqueConstraint,
    event,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class StockBalance(Base):
    __tablename__ = "stock_balances"
    __table_args__ = (
        UniqueConstraint("business_id", "product_id", "location_id"),
        ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        CheckConstraint(
            "typeof(quantity_milli) = 'integer' AND quantity_milli >= 0",
            name="quantity_nonnegative",
        ),
        CheckConstraint("version >= 0", name="version_nonnegative"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str]
    product_id: Mapped[str]
    location_id: Mapped[str]
    quantity_milli: Mapped[int] = mapped_column(default=0)
    version: Mapped[int] = mapped_column(default=0)


class StockMovement(Base):
    __tablename__ = "stock_movements"
    __table_args__ = (
        UniqueConstraint("business_id", "id"),
        UniqueConstraint("business_id", "product_id", "location_id", "balance_version"),
        Index(
            "uq_movement_source",
            "business_id",
            "source_type",
            "source_id",
            unique=True,
            sqlite_where=text("source_id IS NOT NULL"),
        ),
        ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        CheckConstraint(
            "typeof(quantity_milli) = 'integer' AND quantity_milli != 0", name="quantity_nonzero"
        ),
        CheckConstraint(
            "typeof(cost_rupiah) = 'integer' AND cost_rupiah >= 0", name="cost_nonnegative"
        ),
        CheckConstraint(
            "typeof(balance_after_milli) = 'integer' AND balance_after_milli >= 0",
            name="balance_nonnegative",
        ),
        CheckConstraint("balance_version > 0", name="version_positive"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str]
    product_id: Mapped[str]
    location_id: Mapped[str]
    kind: Mapped[str]
    quantity_milli: Mapped[int]
    cost_rupiah: Mapped[int]
    balance_after_milli: Mapped[int]
    balance_version: Mapped[int]
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    occurred_at: Mapped[str]
    posted_at: Mapped[str] = mapped_column(default="")
    note: Mapped[str] = mapped_column(default="")
    source_type: Mapped[str] = mapped_column(default="manual")
    source_id: Mapped[str | None]


@event.listens_for(StockMovement, "before_update")
@event.listens_for(StockMovement, "before_delete")
def reject_movement_change(_mapper, _connection, _target):
    raise ValueError("Stock movements are append-only.")
