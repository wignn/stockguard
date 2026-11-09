from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.investigations.models import InvestigationCase
from stokguard.investigations.schemas import CaseView, FindingsPatch
from stokguard.investigations.service import case_view, get_case, update_findings

router = APIRouter(prefix="/api/v1/businesses/{business_id}/cases", tags=["cases"])


@router.get("")
def history(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        filters = [InvestigationCase.business_id == str(business_id)]
        total = db.scalar(select(func.count()).select_from(InvestigationCase).where(*filters))
        rows = db.scalars(
            select(InvestigationCase)
            .where(*filters)
            .order_by(InvestigationCase.created_at, InvestigationCase.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [case_view(item) for item in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.get("/{case_id}", response_model=CaseView)
def detail(business_id: UUID, case_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        return case_view(get_case(db, actor_in_session(request, db, business_id), case_id))


@router.patch("/{case_id}/findings", response_model=CaseView)
def findings(business_id: UUID, case_id: UUID, payload: FindingsPatch, request: Request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        return update_findings(db, actor, case_id, payload)
