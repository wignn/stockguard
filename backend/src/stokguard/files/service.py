from datetime import datetime
from pathlib import Path
from typing import BinaryIO
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor
from stokguard.core.errors import DomainError
from stokguard.core.transactions import write_uow
from stokguard.files.models import EvidenceFile, EvidenceLink
from stokguard.files.schemas import EvidenceTarget, EvidenceView
from stokguard.files.storage import stage_upload
from stokguard.inventory.ledger import get_movement, validate_actor
from stokguard.investigations.service import get_case


def get_file(db: Session, actor: Actor, file_id: UUID | str) -> EvidenceFile:
    item = db.scalar(
        select(EvidenceFile).where(
            EvidenceFile.id == str(file_id), EvidenceFile.business_id == str(actor.business_id)
        )
    )
    if item is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return item


def evidence_view(db: Session, item: EvidenceFile) -> EvidenceView:
    duplicates = db.scalars(
        select(EvidenceFile.id)
        .where(
            EvidenceFile.business_id == item.business_id,
            EvidenceFile.sha256 == item.sha256,
            EvidenceFile.id != item.id,
        )
        .order_by(EvidenceFile.created_at, EvidenceFile.id)
    ).all()
    links = db.scalars(
        select(EvidenceLink)
        .where(EvidenceLink.business_id == item.business_id, EvidenceLink.file_id == item.id)
        .order_by(EvidenceLink.created_at, EvidenceLink.id)
    ).all()
    return EvidenceView(
        **{
            key: getattr(item, key)
            for key in EvidenceView.model_fields
            if key not in {"duplicate_ids", "links"}
        },
        duplicate_ids=list(duplicates),
        links=[
            {
                "target_type": link.target_type,
                "target_id": link.target_id,
                "created_at": link.created_at,
            }
            for link in links
        ],
    )


def store_upload(
    engine: Engine,
    actor: Actor,
    stream: BinaryIO,
    original_name: str,
    *,
    root: Path,
    now: datetime,
    request_id: str | None = None,
) -> EvidenceView:
    with Session(engine) as db:
        validate_actor(db, actor)
    stored = stage_upload(root, stream, original_name)
    try:
        with write_uow(engine) as db:
            validate_actor(db, actor)
            db.info.update(now=now, request_id=request_id)
            item = EvidenceFile(
                business_id=str(actor.business_id),
                user_id=str(actor.user_id),
                storage_key=stored.key,
                original_name=stored.original_name,
                mime_type=stored.mime_type,
                sha256=stored.sha256,
                size_bytes=stored.size_bytes,
                width=stored.width,
                height=stored.height,
                created_at=now.isoformat(),
            )
            db.add(item)
            db.flush()
            append_event(
                db,
                actor,
                action="evidence_uploaded",
                entity_type="file",
                entity_id=UUID(item.id),
                changes={"sha256": item.sha256},
            )
            result = evidence_view(db, item)
        return result
    except BaseException:
        (root / stored.key).unlink(missing_ok=True)
        raise


def link_evidence(db: Session, actor: Actor, file_id: UUID, target: EvidenceTarget) -> None:
    item = get_file(db, actor, file_id)
    if target.kind == "movement":
        get_movement(db, actor, target.id)
    elif target.kind == "case":
        get_case(db, actor, target.id)
    else:
        from stokguard.approvals.models import CaseSubmission

        submission = db.get(CaseSubmission, str(target.id))
        if submission is None or submission.business_id != str(actor.business_id):
            raise DomainError("not_found", 404, "Data tidak ditemukan.")
        if str(target.id) != db.info.get("creating_submission_id"):
            raise DomainError("immutable_submission", 409, "Tambahkan bukti susulan ke kasus.")
    existing = db.scalar(
        select(EvidenceLink.id).where(
            EvidenceLink.file_id == item.id,
            EvidenceLink.target_type == target.kind,
            EvidenceLink.target_id == str(target.id),
        )
    )
    if existing:
        return
    db.add(
        EvidenceLink(
            business_id=item.business_id,
            file_id=item.id,
            user_id=str(actor.user_id),
            target_type=target.kind,
            target_id=str(target.id),
            **{f"{target.kind}_id": str(target.id)},
            created_at=db.info["now"].isoformat(),
        )
    )
    db.flush()
    append_event(
        db,
        actor,
        action="evidence_linked",
        entity_type=target.kind,
        entity_id=target.id,
        changes={"file_id": item.id},
    )
