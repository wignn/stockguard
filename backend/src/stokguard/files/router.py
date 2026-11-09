from uuid import UUID

from fastapi import APIRouter, Request, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.files.schemas import EvidenceAttach, EvidenceTarget, EvidenceView
from stokguard.files.service import evidence_view, get_file, link_evidence, store_upload
from stokguard.files.storage import content_path

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["evidence"])


@router.post("/files", response_model=EvidenceView, status_code=201)
def upload(business_id: UUID, request: Request, file: UploadFile):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
    return store_upload(
        request.app.state.engine,
        actor,
        file.file,
        file.filename or "bukti",
        root=request.app.state.settings.data_dir / "evidence",
        now=request.app.state.clock.now(),
        request_id=request.state.request_id,
    )


@router.get("/files/{file_id}", response_model=EvidenceView)
def detail(business_id: UUID, file_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        return evidence_view(db, get_file(db, actor_in_session(request, db, business_id), file_id))


@router.get("/files/{file_id}/content")
def content(business_id: UUID, file_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        item = get_file(db, actor_in_session(request, db, business_id), file_id)
        return FileResponse(
            content_path(request.app.state.settings.data_dir / "evidence", item.storage_key),
            media_type=item.mime_type,
            filename=item.original_name,
            headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "private, no-store"},
        )


def attach(business_id, target_id, kind, payload, request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        link_evidence(db, actor, payload.file_id, EvidenceTarget(kind=kind, id=target_id))
        return evidence_view(db, get_file(db, actor, payload.file_id))


@router.post("/cases/{case_id}/evidence", response_model=EvidenceView, status_code=201)
def case_evidence(business_id: UUID, case_id: UUID, payload: EvidenceAttach, request: Request):
    return attach(business_id, case_id, "case", payload, request)


@router.post("/movements/{movement_id}/evidence", response_model=EvidenceView, status_code=201)
def movement_evidence(
    business_id: UUID,
    movement_id: UUID,
    payload: EvidenceAttach,
    request: Request,
):
    return attach(business_id, movement_id, "movement", payload, request)
