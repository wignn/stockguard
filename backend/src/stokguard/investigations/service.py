from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor
from stokguard.core.errors import DomainError
from stokguard.core.numbers import format_quantity, value_delta
from stokguard.investigations.models import InvestigationCase
from stokguard.investigations.schemas import CaseView, FindingsPatch


def get_case(db: Session, actor: Actor, case_id: UUID | str) -> InvestigationCase:
    case = db.scalar(
        select(InvestigationCase).where(
            InvestigationCase.id == str(case_id),
            InvestigationCase.business_id == str(actor.business_id),
        )
    )
    if case is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return case


def _case_evidence(db: Session | None, case: InvestigationCase) -> list:
    if db is None:
        return []
    from stokguard.approvals.models import CaseSubmission
    from stokguard.files.models import EvidenceFile, EvidenceLink
    from stokguard.files.service import evidence_view

    sub_ids = select(CaseSubmission.id).where(
        CaseSubmission.business_id == case.business_id,
        CaseSubmission.case_id == case.id,
    )
    file_ids = (
        select(EvidenceLink.file_id)
        .where(
            EvidenceLink.business_id == case.business_id,
            or_(
                EvidenceLink.case_id == case.id,
                EvidenceLink.submission_id.in_(sub_ids),
            ),
        )
        .distinct()
    )
    files = db.scalars(
        select(EvidenceFile)
        .where(
            EvidenceFile.business_id == case.business_id,
            EvidenceFile.id.in_(file_ids),
        )
        .order_by(EvidenceFile.created_at, EvidenceFile.id)
    ).all()
    return [evidence_view(db, item) for item in files]


def case_view(case: InvestigationCase) -> CaseView:
    db = Session.object_session(case)
    return CaseView(
        id=case.id,
        business_id=case.business_id,
        product_id=case.product_id,
        location_id=case.location_id,
        initial_stocktake_id=case.initial_stocktake_id,
        latest_stocktake_id=case.latest_stocktake_id,
        status=case.status,
        version=case.version,
        difference_quantity=format_quantity(case.difference_milli),
        cost_rupiah=str(case.cost_rupiah),
        estimated_value_rupiah=str(value_delta(case.difference_milli, case.cost_rupiah)),
        created_at=case.created_at,
        updated_at=case.updated_at,
        findings=case.findings,
        current_submission_id=case.current_submission_id,
        evidence=_case_evidence(db, case),
    )


def update_findings(db: Session, actor: Actor, case_id: UUID, command: FindingsPatch) -> CaseView:
    case = get_case(db, actor, case_id)
    if case.status == "resolved" or case.version != command.expected_version:
        raise DomainError(
            "stale_version", 409, "Kasus berubah atau sudah ditutup. Muat ulang data."
        )
    if not command.note.strip():
        raise DomainError("validation_error", 422, "Catatan temuan wajib diisi.")
    case.findings = command.note.strip()
    case.updated_at = db.info["now"].isoformat()
    case.version += 1
    append_event(
        db,
        actor,
        action="findings_updated",
        entity_type="case",
        entity_id=case_id,
        changes={"note": case.findings},
    )
    return case_view(case)
