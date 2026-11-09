from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.orm import Session

from stokguard.audit.models import AuditEvent
from stokguard.auth.dependencies import Actor


def append_event(
    db: Session, actor: Actor, *, action: str, entity_type: str, entity_id: UUID, changes: dict
) -> UUID:
    event = AuditEvent(
        business_id=str(actor.business_id),
        user_id=str(actor.user_id),
        action=action,
        entity_type=entity_type,
        entity_id=str(entity_id),
        changes=changes,
        occurred_at=db.info.get("now", datetime.now(UTC)).isoformat(),
        request_id=db.info.get("request_id"),
    )
    db.add(event)
    db.flush()
    return UUID(event.id)
