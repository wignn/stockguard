from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class EvidenceTarget(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["movement", "case", "submission"]
    id: UUID


class EvidenceAttach(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: UUID


class EvidenceView(BaseModel):
    id: str
    original_name: str
    mime_type: str
    sha256: str
    size_bytes: int
    width: int
    height: int
    created_at: str
    duplicate_ids: list[str]
    links: list[dict]
