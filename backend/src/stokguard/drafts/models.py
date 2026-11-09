from sqlalchemy import JSON, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class TransactionDraft(Base):
    __tablename__ = "transaction_drafts"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"))
    ocr_job_id: Mapped[str | None] = mapped_column(ForeignKey("ocr_jobs.id"), unique=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    receipt_number: Mapped[str | None]
    receipt_date: Mapped[str | None]
    original_ocr: Mapped[dict | None] = mapped_column(JSON)
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str]


class DraftLine(Base):
    __tablename__ = "draft_lines"
    __table_args__ = (UniqueConstraint("draft_id", "position"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    draft_id: Mapped[str] = mapped_column(ForeignKey("transaction_drafts.id"))
    position: Mapped[int]
    suggestion: Mapped[dict | None] = mapped_column(JSON)
    product_id: Mapped[str | None] = mapped_column(ForeignKey("products.id"))
    kind: Mapped[str | None]
    quantity: Mapped[str | None]
    unit_price_rupiah: Mapped[str | None]
    occurred_at: Mapped[str | None]
    note: Mapped[str] = mapped_column(default="")
    status: Mapped[str] = mapped_column(default="pending")
    version: Mapped[int] = mapped_column(default=1)
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("stock_movements.id"), unique=True)
