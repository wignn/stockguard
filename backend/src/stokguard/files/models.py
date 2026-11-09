from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class EvidenceFile(Base):
    __tablename__ = "evidence_files"
    __table_args__ = (UniqueConstraint("business_id", "id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    storage_key: Mapped[str] = mapped_column(unique=True)
    original_name: Mapped[str]
    mime_type: Mapped[str]
    sha256: Mapped[str]
    size_bytes: Mapped[int]
    width: Mapped[int]
    height: Mapped[int]
    created_at: Mapped[str]


class EvidenceLink(Base):
    __tablename__ = "evidence_links"
    __table_args__ = (
        UniqueConstraint("file_id", "target_type", "target_id"),
        CheckConstraint(
            "(movement_id IS NOT NULL) + (case_id IS NOT NULL) + (submission_id IS NOT NULL) = 1",
            name="one_evidence_target",
        ),
    )
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    target_type: Mapped[str]
    target_id: Mapped[str]
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("stock_movements.id"))
    case_id: Mapped[str | None] = mapped_column(ForeignKey("investigation_cases.id"))
    submission_id: Mapped[str | None] = mapped_column(ForeignKey("case_submissions.id"))
    created_at: Mapped[str]
