import hashlib
import json
from uuid import UUID

from sqlalchemy import ForeignKey, UniqueConstraint, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from stokguard.auth.dependencies import Actor
from stokguard.auth.models import new_id
from stokguard.core.db import Base
from stokguard.core.errors import DomainError


class IdempotencyRecord(Base):
    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("business_id", "user_id", "operation", "key"),)
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    operation: Mapped[str]
    key: Mapped[str]
    request_hash: Mapped[str]
    result_id: Mapped[str]


def request_digest(payload: dict) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(encoded.encode()).hexdigest()


def find_replay(db: Session, actor: Actor, operation: str, key: UUID, digest: str) -> str | None:
    record = db.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.business_id == str(actor.business_id),
            IdempotencyRecord.user_id == str(actor.user_id),
            IdempotencyRecord.operation == operation,
            IdempotencyRecord.key == str(key),
        )
    )
    if record is None:
        return None
    if record.request_hash != digest:
        raise DomainError(
            "idempotency_conflict", 409, "Kunci permintaan sudah digunakan untuk data berbeda."
        )
    return record.result_id


def save_result(db: Session, actor: Actor, operation: str, key: UUID, digest: str, result_id: str):
    db.add(
        IdempotencyRecord(
            business_id=str(actor.business_id),
            user_id=str(actor.user_id),
            operation=operation,
            key=str(key),
            request_hash=digest,
            result_id=result_id,
        )
    )
    db.flush()
