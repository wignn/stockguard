from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.approvals.models import CaseSubmission, ReversalRequest
from stokguard.approvals.schemas import (
    DecisionCreate,
    DecisionView,
    ReversalCreate,
    ReversalDecision,
    SubmissionCreate,
    SubmissionView,
)
from stokguard.approvals.service import (
    RecountRequired,
    decide_case_in_session,
    decide_reversal,
    get_reversal,
    mark_recount_required,
    request_reversal,
    reversal_view,
    submission_view,
    submit_case,
)
from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.investigations.service import get_case

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["approvals"])
Key = Annotated[UUID, Header(alias="Idempotency-Key")]


def prepare(db, request, business_id):
    actor = actor_in_session(request, db, business_id)
    db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
    return actor


@router.post("/cases/{case_id}/submissions", status_code=201, response_model=SubmissionView)
def submit(business_id: UUID, case_id: UUID, payload: SubmissionCreate, request: Request):
    pending = None
    with write_uow(request.app.state.engine) as db:
        actor = prepare(db, request, business_id)
        try:
            result = submit_case(db, actor, case_id, payload)
        except RecountRequired as exc:
            mark_recount_required(db, actor, exc)
            pending = exc
    if pending:
        raise pending
    return result


@router.get("/cases/{case_id}/submissions")
def submissions(
    business_id: UUID,
    case_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        get_case(db, actor, case_id)
        filters = [
            CaseSubmission.business_id == str(business_id),
            CaseSubmission.case_id == str(case_id),
        ]
        total = db.scalar(select(func.count()).select_from(CaseSubmission).where(*filters))
        rows = db.scalars(
            select(CaseSubmission)
            .where(*filters)
            .order_by(CaseSubmission.case_version.desc())
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [submission_view(item) for item in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.post("/cases/{case_id}/decisions", response_model=DecisionView)
def decision(
    business_id: UUID,
    case_id: UUID,
    payload: DecisionCreate,
    request: Request,
    idempotency_key: Key,
):
    pending = None
    with write_uow(request.app.state.engine) as db:
        actor = prepare(db, request, business_id)
        try:
            result = decide_case_in_session(db, actor, case_id, payload, idempotency_key)
        except RecountRequired as exc:
            mark_recount_required(db, actor, exc)
            pending = exc
    if pending:
        raise pending
    return result


@router.post("/movements/{movement_id}/reversal-requests", status_code=201)
def reversal(business_id: UUID, movement_id: UUID, payload: ReversalCreate, request: Request):
    with write_uow(request.app.state.engine) as db:
        return request_reversal(db, prepare(db, request, business_id), movement_id, payload)


@router.get("/reversal-requests")
def reversal_list(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        filters = [ReversalRequest.business_id == str(business_id)]
        total = db.scalar(select(func.count()).select_from(ReversalRequest).where(*filters))
        rows = db.scalars(
            select(ReversalRequest)
            .where(*filters)
            .order_by(ReversalRequest.created_at.desc(), ReversalRequest.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [reversal_view(item) for item in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.get("/reversal-requests/{reversal_id}")
def reversal_detail(business_id: UUID, reversal_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        return reversal_view(
            get_reversal(db, actor_in_session(request, db, business_id), reversal_id)
        )


@router.post("/reversal-requests/{reversal_id}/decisions", response_model=DecisionView)
def reversal_decision(
    business_id: UUID,
    reversal_id: UUID,
    payload: ReversalDecision,
    request: Request,
    idempotency_key: Key,
):
    with write_uow(request.app.state.engine) as db:
        return decide_reversal(
            db, prepare(db, request, business_id), reversal_id, payload, idempotency_key
        )
