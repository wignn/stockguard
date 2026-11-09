from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor
from stokguard.core.errors import DomainError
from stokguard.files.service import get_file
from stokguard.ocr.models import OcrJob
from stokguard.ocr.schemas import JobLease, ParsedReceipt


def job_view(job: OcrJob) -> dict:
    return {
        key: getattr(job, key)
        for key in [
            "id",
            "file_id",
            "retry_of_id",
            "status",
            "attempts",
            "error_code",
            "result",
            "created_at",
            "finished_at",
        ]
    }


def get_job(db: Session, actor: Actor, job_id: UUID | str) -> OcrJob:
    job = db.scalar(
        select(OcrJob).where(
            OcrJob.id == str(job_id),
            OcrJob.business_id == str(actor.business_id),
        )
    )
    if job is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return job


def enqueue(db: Session, actor: Actor, file_id: UUID, retry_of: OcrJob | None = None) -> dict:
    get_file(db, actor, file_id)
    if retry_of is not None and retry_of.status != "failed":
        raise DomainError("ocr_not_failed", 409, "Hanya pekerjaan gagal yang dapat dicoba ulang.")
    job = OcrJob(
        business_id=str(actor.business_id),
        user_id=str(actor.user_id),
        file_id=str(file_id),
        retry_of_id=retry_of.id if retry_of else None,
        created_at=db.info["now"].isoformat(),
    )
    db.add(job)
    db.flush()
    append_event(
        db,
        actor,
        action="ocr_queued",
        entity_type="ocr_job",
        entity_id=UUID(job.id),
        changes={"file_id": job.file_id, "retry_of_id": job.retry_of_id},
    )
    return job_view(job)


def claim_job(db: Session, now: datetime) -> JobLease | None:
    timestamp = now.isoformat()
    expired = db.scalars(
        select(OcrJob).where(
            OcrJob.status == "processing",
            OcrJob.lease_expires_at <= timestamp,
        )
    ).all()
    for job in expired:
        if job.attempts >= 2:
            job.status, job.error_code, job.finished_at = "failed", "lease_expired", timestamp
            job.fencing_token = None
        else:
            job.status = "queued"
    db.flush()
    job = db.scalar(
        select(OcrJob)
        .where(OcrJob.status == "queued")
        .order_by(OcrJob.created_at, OcrJob.id)
        .limit(1)
    )
    if job is None:
        return None
    token, expires = uuid4().hex, now + timedelta(seconds=120)
    job.status, job.fencing_token, job.lease_expires_at = "processing", token, expires.isoformat()
    job.attempts += 1
    job.error_code = None
    db.flush()
    return JobLease(job.id, token, expires)


def finish_job(db: Session, lease: JobLease, *, result: dict | None, error: str | None) -> bool:
    now = db.info.get("now", datetime.now(UTC))
    changed = db.execute(
        update(OcrJob)
        .where(
            OcrJob.id == lease.job_id,
            OcrJob.status == "processing",
            OcrJob.fencing_token == lease.fencing_token,
            OcrJob.lease_expires_at > now.isoformat(),
        )
        .values(
            status="failed" if error else "succeeded",
            result=result,
            error_code=error,
            finished_at=now.isoformat(),
            fencing_token=None,
        )
    )
    return changed.rowcount == 1


def complete_job(db: Session, lease: JobLease, result: ParsedReceipt) -> bool:
    from stokguard.drafts.service import create_from_ocr

    if not finish_job(db, lease, result=result.model_dump(mode="json"), error=None):
        return False
    create_from_ocr(db, db.get(OcrJob, lease.job_id), result)
    return True


def fail_job(db: Session, lease: JobLease, error: str) -> bool:
    return finish_job(db, lease, result=None, error=error)
