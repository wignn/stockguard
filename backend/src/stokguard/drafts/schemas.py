from datetime import date
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

MovementKind = Literal["opening", "inbound", "sale", "damage", "customer_return", "supplier_return"]


class LineValues(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID | None = None
    kind: MovementKind | None = None
    quantity: str | None = Field(default=None, max_length=30)
    unit_price_rupiah: str | None = Field(default=None, max_length=30)
    occurred_at: AwareDatetime | None = None
    note: str = Field(default="", max_length=2000)


class LinePatch(LineValues):
    expected_version: int = Field(ge=1, strict=True)


class DraftCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    file_id: UUID
    receipt_number: str | None = Field(default=None, max_length=100)
    receipt_date: date | None = None
    lines: list[LineValues] = Field(
        default_factory=lambda: [LineValues()], min_length=1, max_length=100
    )


class DraftPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    receipt_number: str | None = Field(default=None, max_length=100)
    receipt_date: date | None = None


class DraftConfirm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_line_version: int = Field(ge=1, strict=True)
    expected_balance_version: int = Field(ge=0, strict=True)
    reviewed: Literal[True]
