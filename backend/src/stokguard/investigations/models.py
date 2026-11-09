from sqlalchemy import ForeignKey, ForeignKeyConstraint, Index, text
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class InvestigationCase(Base):
    __tablename__ = "investigation_cases"
    __table_args__ = (
        ForeignKeyConstraint(
            ["business_id", "product_id"], ["products.business_id", "products.id"]
        ),
        ForeignKeyConstraint(
            ["business_id", "location_id"], ["locations.business_id", "locations.id"]
        ),
        Index(
            "uq_unresolved_case",
            "business_id",
            "product_id",
            "location_id",
            unique=True,
            sqlite_where=text("status != 'resolved'"),
        ),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str]
    product_id: Mapped[str]
    location_id: Mapped[str]
    initial_stocktake_id: Mapped[str] = mapped_column(ForeignKey("stocktakes.id"))
    latest_stocktake_id: Mapped[str] = mapped_column(ForeignKey("stocktakes.id"))
    status: Mapped[str] = mapped_column(default="investigating")
    version: Mapped[int] = mapped_column(default=1)
    difference_milli: Mapped[int]
    cost_rupiah: Mapped[int]
    created_at: Mapped[str]
    updated_at: Mapped[str]
    findings: Mapped[str] = mapped_column(default="")
    current_submission_id: Mapped[str | None]
