from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal

from pydantic import BaseModel


@dataclass
class RiskFacts:
    now: datetime
    timezone: str
    cases: list[tuple[str, datetime, int]] = field(default_factory=list)
    corrections: list[tuple[str, datetime, int, bool, str]] = field(default_factory=list)
    counts: list[tuple[datetime, int]] = field(default_factory=list)
    active_case: bool = False


class RiskAssessment(BaseModel):
    priority: Literal["high", "medium", "low", "insufficient"]
    reasons: list[str]
    policy_version: str = "rules-v1"
    window_start: datetime
    window_end: datetime
    history_sufficient: bool
    case_count: int
    missing_evidence_corrections: int
