from sqlalchemy import CheckConstraint, ForeignKey, ForeignKeyConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class Stocktake(Base):
    __tablename__ = "stocktakes"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        CheckConstraint(
            "baseline_milli >= 0 AND baseline_version >= 0", name="baseline_nonnegative"
        ),
        CheckConstraint(
            "counted_milli IS NULL OR (typeof(counted_milli) = 'integer' AND counted_milli >= 0)",
            name="count_nonnegative",
        ),
        Index(
            "uq_active_stocktake",
            "business_id",
            "product_id",
            "location_id",
            unique=True,
            sqlite_where=text("status = 'active'"),
        ),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str]
    product_id: Mapped[str]
    location_id: Mapped[str]
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    status: Mapped[str] = mapped_column(default="active")
    version: Mapped[int] = mapped_column(default=1)
    baseline_milli: Mapped[int]
    baseline_version: Mapped[int]
    cost_rupiah: Mapped[int]
    started_at: Mapped[str]
    expires_at: Mapped[str]
    finalized_at: Mapped[str | None]
    counted_milli: Mapped[int | None]
    difference_milli: Mapped[int | None]
    recounted: Mapped[bool] = mapped_column(default=False)
    rack_checked: Mapped[bool] = mapped_column(default=False)
    storage_checked: Mapped[bool] = mapped_column(default=False)
    no_physical_movement: Mapped[bool] = mapped_column(default=False)
    note: Mapped[str] = mapped_column(default="")
