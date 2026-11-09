from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class SubmissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_case_version: int = Field(ge=1, strict=True)
    stocktake_id: UUID
    cause: Literal["unrecorded_transaction", "damage_return", "miscount", "unknown"]
    resolution_kind: Literal["movement", "adjustment", "no_movement"]
    quantity: str
    movement_kind: (
        Literal["inbound", "sale", "damage", "customer_return", "supplier_return"] | None
    ) = None
    occurred_at: AwareDatetime
    note: str = Field(min_length=1, max_length=2000)
    missing_evidence_reason: str = Field(default="", max_length=2000)
    evidence_ids: list[UUID] = Field(default_factory=list, max_length=20)


class SubmissionView(BaseModel):
    id: str
    case_id: str
    stocktake_id: str
    user_id: str
    case_version: int
    cause: str
    resolution_kind: str
    quantity: str
    movement_kind: str | None
    occurred_at: str
    note: str
    missing_evidence_reason: str
    submitted_at: str
    snapshot: dict


class DecisionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_case_version: int = Field(ge=1, strict=True)
    submission_id: UUID
    decision: Literal["approve", "reject", "recount"]
    note: str = Field(default="", max_length=2000)


class DecisionView(BaseModel):
    id: str
    target_type: str
    target_id: str
    submission_id: str | None
    decision: str
    note: str
    movement_id: str | None
    case_status: str
    decided_at: str
    snapshot: dict


class ReversalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=2000)
    expected_balance_version: int = Field(ge=0, strict=True)


class ReversalDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_request_version: int = Field(ge=1, strict=True)
    expected_balance_version: int = Field(ge=0, strict=True)
    decision: Literal["approve", "reject"]
    note: str = Field(default="", max_length=2000)
