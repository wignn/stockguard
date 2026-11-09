from sqlalchemy import ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class Business(Base):
    __tablename__ = "businesses"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    name: Mapped[str]
    timezone: Mapped[str] = mapped_column(default="Asia/Jakarta")
    is_demo: Mapped[bool] = mapped_column(default=False)


class Location(Base):
    __tablename__ = "locations"
    __table_args__ = (UniqueConstraint("business_id"), UniqueConstraint("business_id", "id"))
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    name: Mapped[str] = mapped_column(default="Lokasi Utama")
