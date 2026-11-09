from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.audit.export import audit_filters, parse_time_bounds, stream_audit_csv
from stokguard.audit.models import AuditEvent
from stokguard.auth.dependencies import actor_in_session

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["audit"])


@router.get("/audit-events")
def history(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        start_utc, end_utc = parse_time_bounds(db, business_id, from_, to)
        filters = audit_filters(business_id, start_utc, end_utc)
        total = db.scalar(select(func.count()).select_from(AuditEvent).where(*filters))
        rows = db.scalars(
            select(AuditEvent)
            .where(*filters)
            .order_by(AuditEvent.occurred_at.desc(), AuditEvent.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [
                {
                    "id": e.id,
                    "user_id": e.user_id,
                    "action": e.action,
                    "entity_type": e.entity_type,
                    "entity_id": e.entity_id,
                    "occurred_at": e.occurred_at,
                    "changes": e.changes,
                    "request_id": e.request_id,
                }
                for e in rows
            ],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.get("/exports/audit.csv")
def export_csv(
    business_id: UUID,
    request: Request,
    from_: str | None = Query(None, alias="from"),
    to: str | None = Query(None),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        start_utc, end_utc = parse_time_bounds(db, business_id, from_, to)
    return StreamingResponse(
        stream_audit_csv(request.app.state.engine, business_id, start_utc, end_utc),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": 'attachment; filename="audit.csv"',
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "private, no-store",
        },
    )
