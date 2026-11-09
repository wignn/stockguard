from sqlalchemy import JSON, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from stokguard.auth.models import new_id
from stokguard.core.db import Base


class OcrJob(Base):
    __tablename__ = "ocr_jobs"
    id: Mapped[str] = mapped_column(primary_key=True, default=new_id)
    business_id: Mapped[str] = mapped_column(ForeignKey("businesses.id"))
    file_id: Mapped[str] = mapped_column(ForeignKey("evidence_files.id"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"))
    retry_of_id: Mapped[str | None] = mapped_column(ForeignKey("ocr_jobs.id"))
    status: Mapped[str] = mapped_column(default="queued")
    attempts: Mapped[int] = mapped_column(default=0)
    fencing_token: Mapped[str | None]
    lease_expires_at: Mapped[str | None]
    error_code: Mapped[str | None]
    result: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[str]
    finished_at: Mapped[str | None]
