from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ParsedLine(BaseModel):
    name: str
    quantity: str
    price_rupiah: str


class ParsedReceipt(BaseModel):
    raw_text: str
    receipt_number: str | None = None
    receipt_date: str | None = None
    lines: list[ParsedLine] = Field(default_factory=list)


class JobCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: UUID


@dataclass(frozen=True)
class JobLease:
    job_id: str
    fencing_token: str
    expires_at: datetime
