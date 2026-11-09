from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.businesses.models import Business
from stokguard.investigations.models import InvestigationCase
from stokguard.risk.schemas import RiskAssessment, RiskFacts
from stokguard.stocktakes.models import Stocktake


def assess_priority(facts: RiskFacts) -> RiskAssessment:
    start = facts.now - timedelta(days=30)
    cases = {
        case_id
        for case_id, timestamp, difference in facts.cases
        if start <= timestamp <= facts.now and difference != 0
    }
    corrections = {
        item_id
        for item_id, timestamp, quantity, missing, kind in facts.corrections
        if start <= timestamp <= facts.now and quantity < 0 and missing and kind == "adjustment_out"
    }
    counts = sorted(
        ((stamp, difference) for stamp, difference in facts.counts if start <= stamp <= facts.now),
        reverse=True,
    )[:3]
    dates = {stamp.astimezone(ZoneInfo(facts.timezone)).date() for stamp, _ in counts}
    sufficient = len(counts) == 3 and len(dates) == 3
    if len(cases) >= 3 or len(corrections) >= 3:
        priority = "high"
        reasons = []
        if len(cases) >= 3:
            reasons.append(f"{len(cases)} kasus selisih berbeda dalam 30 hari.")
        if len(corrections) >= 3:
            reasons.append(f"{len(corrections)} koreksi pengurangan tanpa bukti saat keputusan.")
    elif facts.active_case:
        priority, reasons = "medium", ["Ada kasus selisih yang belum diselesaikan."]
    elif sufficient and all(difference == 0 for _, difference in counts):
        priority, reasons = (
            "low",
            ["Tiga opname terakhir pada tanggal berbeda cocok; tidak ada kasus aktif."],
        )
    else:
        priority, reasons = (
            "insufficient",
            ["Riwayat belum cukup untuk menetapkan prioritas rendah."],
        )
    return RiskAssessment(
        priority=priority,
        reasons=reasons,
        window_start=start,
        window_end=facts.now,
        history_sufficient=sufficient,
        case_count=len(cases),
        missing_evidence_corrections=len(corrections),
    )


def product_risk(db: Session, business_id: str, product_id: str, now: datetime) -> RiskAssessment:
    # Import here to keep policy evaluation independent of the approval write path.
    from stokguard.approvals.models import ApprovalDecision
    from stokguard.inventory.models import StockMovement

    business = db.get(Business, business_id)
    cases = db.scalars(
        select(InvestigationCase).where(
            InvestigationCase.business_id == business_id, InvestigationCase.product_id == product_id
        )
    ).all()
    facts = RiskFacts(
        now=now, timezone=business.timezone, active_case=any(c.status != "resolved" for c in cases)
    )
    for case in cases:
        initial = db.get(Stocktake, case.initial_stocktake_id)
        facts.cases.append(
            (case.id, datetime.fromisoformat(initial.finalized_at), initial.difference_milli)
        )
    for count in db.scalars(
        select(Stocktake).where(
            Stocktake.business_id == business_id,
            Stocktake.product_id == product_id,
            Stocktake.status == "finalized",
        )
    ):
        facts.counts.append((datetime.fromisoformat(count.finalized_at), count.difference_milli))
    rows = db.execute(
        select(ApprovalDecision, StockMovement)
        .join(StockMovement, ApprovalDecision.movement_id == StockMovement.id)
        .where(
            ApprovalDecision.business_id == business_id,
            StockMovement.business_id == business_id,
            StockMovement.product_id == product_id,
            ApprovalDecision.decision == "approve",
        )
    )
    for decision, movement in rows:
        facts.corrections.append(
            (
                decision.id,
                datetime.fromisoformat(decision.decided_at),
                movement.quantity_milli,
                bool(decision.snapshot.get("missing_evidence")),
                movement.kind,
            )
        )
    return assess_priority(facts)
