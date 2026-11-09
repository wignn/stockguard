from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class CountStart(BaseModel):
    model_config = ConfigDict(extra="forbid")
    product_id: UUID


class CountFinalize(BaseModel):
    model_config = ConfigDict(extra="forbid")
    counted_quantity: str
    expected_version: int = Field(ge=1, strict=True)
    recounted: bool = Field(strict=True)
    rack_checked: bool = Field(strict=True)
    storage_checked: bool = Field(strict=True)
    no_physical_movement: bool = Field(strict=True)


class CountAction(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    note: str = Field(default="", max_length=2000)


class StocktakeView(BaseModel):
    id: str
    business_id: str
    product_id: str
    location_id: str
    user_id: str
    status: str
    version: int
    baseline_quantity: str
    baseline_version: int
    counted_quantity: str | None
    difference_quantity: str | None
    difference_percentage: str | None
    started_at: str
    expires_at: str
    finalized_at: str | None
    case_id: str | None = None


class StocktakeResult(StocktakeView):
    pass
