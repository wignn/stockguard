from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from threading import Event

from PIL import Image, ImageOps
from sqlalchemy.orm import Session

from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.errors import DomainError
from stokguard.core.maintenance import (
    acknowledge_worker_pause,
    maintenance_status,
    operation_slot,
)
from stokguard.core.transactions import write_uow
from stokguard.files.models import EvidenceFile
from stokguard.files.storage import content_path
from stokguard.ocr.engine import OcrEngine, OcrFailure
from stokguard.ocr.jobs import claim_job, complete_job, fail_job
from stokguard.ocr.models import OcrJob
from stokguard.ocr.parser import parse_receipt


def process_one(settings: Settings, engine: OcrEngine, *, now: datetime | None = None) -> bool:
    if maintenance_status(settings)["active"]:
        acknowledge_worker_pause(settings)
        return False

    database = make_engine(settings.database_path)

    def current():
        return now or datetime.now(UTC)

    try:
        try:
            with operation_slot(settings, "ocr-claim"):
                with write_uow(database) as db:
                    lease = claim_job(db, current())
        except DomainError:
            acknowledge_worker_pause(settings)
            return False

        if lease is None:
            return False
        try:
            with Session(database) as db:
                job = db.get(OcrJob, lease.job_id)
                item = db.get(EvidenceFile, job.file_id)
                path = content_path(settings.data_dir / "evidence", item.storage_key)
            with TemporaryDirectory(prefix="ocr-", dir=settings.data_dir) as temporary:
                derivative = Path(temporary) / "oriented.png"
                with Image.open(path) as image:
                    if image.width * image.height > 20_000_000:
                        raise OcrFailure("invalid_image")
                    ImageOps.exif_transpose(image).convert("RGB").save(derivative)
                recognized = engine.recognize(derivative, 60)
                result = parse_receipt(recognized.text)

            with operation_slot(settings, "ocr-complete"):
                with write_uow(database) as db:
                    db.info["now"] = current()
                    complete_job(db, lease, result)
        except DomainError:
            # Maintenance activated while OCR subprocess was running: pause cleanly
            # and let the job's lease recover on resume without committing partial state.
            acknowledge_worker_pause(settings)
            return False
        except Exception as exc:
            try:
                with operation_slot(settings, "ocr-fail"):
                    with write_uow(database) as db:
                        db.info["now"] = current()
                        fail_job(
                            db,
                            lease,
                            exc.code if isinstance(exc, OcrFailure) else "ocr_failed",
                        )
            except DomainError:
                acknowledge_worker_pause(settings)
                return False
        return True
    finally:
        database.dispose()


def run_worker(settings: Settings, engine: OcrEngine, stop: Event | None = None) -> None:
    stop = stop or Event()
    while not stop.is_set():
        if maintenance_status(settings)["active"]:
            acknowledge_worker_pause(settings)
            stop.wait(0.1)
            continue
        if not process_one(settings, engine):
            stop.wait(0.2)
