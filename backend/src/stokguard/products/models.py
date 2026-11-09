from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class Product(Base):
    __tablename__ = "products"
    __table_args__ = (
        UniqueConstraint("business_id", "sku"),
        UniqueConstraint("business_id", "id"),
        CheckConstraint("typeof(step_milli) = 'integer' AND step_milli > 0", name="step_positive"),
        CheckConstraint(
            "typeof(cost_rupiah) = 'integer' AND cost_rupiah >= 0", name="cost_nonnegative"
        ),
        CheckConstraint("version >= 1", name="version_positive"),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    sku: Mapped[str]
    name: Mapped[str]
    unit: Mapped[str]
    step_milli: Mapped[int]
    cost_rupiah: Mapped[int]
    active: Mapped[bool] = mapped_column(default=True)
    version: Mapped[int] = mapped_column(default=1)
