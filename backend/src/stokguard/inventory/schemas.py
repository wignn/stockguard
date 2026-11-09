from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field


class MovementCommand(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID
    kind: Literal["opening", "inbound", "sale", "damage", "customer_return", "supplier_return"]
    quantity: str
    occurred_at: AwareDatetime
    note: str = Field(default="", max_length=2000)
    expected_balance_version: int = Field(ge=0, strict=True)


class ApprovedMovementCommand(MovementCommand):
    kind: Literal[
        "opening",
        "inbound",
        "sale",
        "damage",
        "customer_return",
        "supplier_return",
        "adjustment_in",
        "adjustment_out",
    ]


@dataclass(frozen=True)
class MovementSource:
    kind: Literal["manual", "draft_line", "case", "reversal"] = "manual"
    id: UUID | None = None


class MovementView(BaseModel):
    id: str
    business_id: str
    product_id: str
    location_id: str
    kind: str
    quantity: str
    cost_rupiah: str
    balance_quantity: str
    balance_version: int
    occurred_at: datetime
    posted_at: datetime
    note: str
    source_type: str
    source_id: str | None
