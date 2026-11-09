from pydantic import BaseModel, ConfigDict, Field

from stokguard.files.schemas import EvidenceView


class FindingsPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_version: int = Field(ge=1, strict=True)
    note: str = Field(min_length=1, max_length=5000)


class CaseView(BaseModel):
    id: str
    business_id: str
    product_id: str
    location_id: str
    initial_stocktake_id: str
    latest_stocktake_id: str
    status: str
    version: int
    difference_quantity: str
    cost_rupiah: str
    estimated_value_rupiah: str
    created_at: str
    updated_at: str
    findings: str
    current_submission_id: str | None
    evidence: list[EvidenceView] = Field(default_factory=list)
