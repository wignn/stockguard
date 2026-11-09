from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.ocr.jobs import enqueue, get_job, job_view
from stokguard.ocr.schemas import JobCreate

router = APIRouter(prefix="/api/v1/businesses/{business_id}/ocr-jobs", tags=["ocr"])


@router.post("", status_code=201)
def create(business_id: UUID, payload: JobCreate, request: Request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        return enqueue(db, actor, payload.file_id)


@router.get("/{job_id}")
def detail(business_id: UUID, job_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        return job_view(get_job(db, actor_in_session(request, db, business_id), job_id))


@router.post("/{job_id}/retry", status_code=201)
def retry(business_id: UUID, job_id: UUID, request: Request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        original = get_job(db, actor, job_id)
        return enqueue(db, actor, UUID(original.file_id), retry_of=original)
