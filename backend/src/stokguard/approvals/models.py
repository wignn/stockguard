from sqlalchemy import JSON, ForeignKey, UniqueConstraint, event
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class CaseSubmission(Base):
    __tablename__ = "case_submissions"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    case_id: Mapped[str] = mapped_column(ForeignKey("investigation_cases.id"))
    stocktake_id: Mapped[str] = mapped_column(ForeignKey("stocktakes.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    case_version: Mapped[int]
    cause: Mapped[str]
    resolution_kind: Mapped[str]
    quantity_milli: Mapped[int]
    movement_kind: Mapped[str | None]
    occurred_at: Mapped[str]
    note: Mapped[str]
    missing_evidence_reason: Mapped[str]
    submitted_at: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class ApprovalDecision(Base):
    __tablename__ = "approval_decisions"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    target_type: Mapped[str]
    target_id: Mapped[str]
    submission_id: Mapped[str | None]
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    decision: Mapped[str]
    note: Mapped[str]
    movement_id: Mapped[str | None] = mapped_column(ForeignKey("stock_movements.id"))
    case_status: Mapped[str]
    decided_at: Mapped[str]
    snapshot: Mapped[dict] = mapped_column(JSON, default=dict)


class ReversalRequest(Base):
    __tablename__ = "reversal_requests"
    __table_args__ = (UniqueConstraint("business_id", "original_movement_id"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    original_movement_id: Mapped[str] = mapped_column(ForeignKey("stock_movements.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    reason: Mapped[str]
    status: Mapped[str] = mapped_column(default="pending_review")
    version: Mapped[int] = mapped_column(default=1)
    created_at: Mapped[str]


@event.listens_for(CaseSubmission, "before_update")
@event.listens_for(CaseSubmission, "before_delete")
@event.listens_for(ApprovalDecision, "before_update")
@event.listens_for(ApprovalDecision, "before_delete")
def reject_history_change(_mapper, _connection, _target):
    raise ValueError("Submitted history is append-only.")
