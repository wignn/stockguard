from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.drafts.models import TransactionDraft
from stokguard.drafts.schemas import DraftConfirm, DraftCreate, DraftPatch, LinePatch
from stokguard.drafts.service import (
    confirm_in_session,
    create_draft,
    draft_view,
    get_draft,
    patch_draft,
    patch_line,
)
from stokguard.inventory.schemas import MovementView

router = APIRouter(prefix="/api/v1/businesses/{business_id}/transaction-drafts", tags=["drafts"])


def prepare(db, request, business_id):
    actor = actor_in_session(request, db, business_id)
    db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
    return actor


@router.get("")
def listing(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        filters = [TransactionDraft.business_id == str(business_id)]
        total = db.scalar(select(func.count()).select_from(TransactionDraft).where(*filters))
        rows = db.scalars(
            select(TransactionDraft)
            .where(*filters)
            .order_by(TransactionDraft.created_at.desc(), TransactionDraft.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [draft_view(db, row) for row in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.post("", status_code=201)
def create(business_id: UUID, payload: DraftCreate, request: Request):
    with write_uow(request.app.state.engine) as db:
        return create_draft(db, prepare(db, request, business_id), payload)


@router.get("/{draft_id}")
def detail(business_id: UUID, draft_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        return draft_view(db, get_draft(db, actor_in_session(request, db, business_id), draft_id))


@router.patch("/{draft_id}")
def patch(business_id: UUID, draft_id: UUID, payload: DraftPatch, request: Request):
    with write_uow(request.app.state.engine) as db:
        return patch_draft(db, prepare(db, request, business_id), draft_id, payload)


@router.patch("/{draft_id}/lines/{line_id}")
def edit_line(
    business_id: UUID, draft_id: UUID, line_id: UUID, payload: LinePatch, request: Request
):
    with write_uow(request.app.state.engine) as db:
        return patch_line(db, prepare(db, request, business_id), draft_id, line_id, payload)


@router.post("/{draft_id}/lines/{line_id}/confirm", response_model=MovementView, status_code=201)
def confirm(
    business_id: UUID,
    draft_id: UUID,
    line_id: UUID,
    payload: DraftConfirm,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
):
    with write_uow(request.app.state.engine) as db:
        return confirm_in_session(
            db, prepare(db, request, business_id), draft_id, line_id, payload, idempotency_key
        )
