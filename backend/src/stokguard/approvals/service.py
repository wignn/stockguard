from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from stokguard.approvals.models import ApprovalDecision, CaseSubmission, ReversalRequest
from stokguard.approvals.schemas import (
    DecisionCreate,
    DecisionView,
    ReversalCreate,
    ReversalDecision,
    SubmissionCreate,
    SubmissionView,
)
from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor, require_owner
from stokguard.core.errors import DomainError
from stokguard.core.numbers import format_quantity, parse_quantity
from stokguard.core.transactions import write_uow
from stokguard.inventory.idempotency import find_replay, request_digest, save_result
from stokguard.inventory.ledger import book_movement, get_movement, validate_actor
from stokguard.inventory.models import StockBalance
from stokguard.inventory.schemas import ApprovedMovementCommand, MovementSource
from stokguard.investigations.service import get_case
from stokguard.products.service import get_product
from stokguard.risk.service import product_risk
from stokguard.stocktakes.service import ensure_no_active_count, get_stocktake


class RecountRequired(DomainError):
    def __init__(self, case_id: str):
        super().__init__(
            "recount_required", 409, "Ada transaksi baru sejak opname. Hitung ulang diperlukan."
        )
        self.case_id = case_id


def submission_view(item: CaseSubmission) -> SubmissionView:
    return SubmissionView(
        id=item.id,
        case_id=item.case_id,
        stocktake_id=item.stocktake_id,
        user_id=item.user_id,
        case_version=item.case_version,
        cause=item.cause,
        resolution_kind=item.resolution_kind,
        quantity=format_quantity(item.quantity_milli),
        movement_kind=item.movement_kind,
        occurred_at=item.occurred_at,
        note=item.note,
        missing_evidence_reason=item.missing_evidence_reason,
        submitted_at=item.submitted_at,
        snapshot=item.snapshot,
    )


def decision_view(item: ApprovalDecision) -> DecisionView:
    return DecisionView(**{key: getattr(item, key) for key in DecisionView.model_fields})


def balance_for(db, business_id, product_id):
    return db.scalar(
        select(StockBalance).where(
            StockBalance.business_id == business_id, StockBalance.product_id == product_id
        )
    )


def submit_case(
    db: Session, actor: Actor, case_id: UUID, command: SubmissionCreate
) -> SubmissionView:
    case = get_case(db, actor, case_id)
    if (
        case.status in {"resolved", "needs_recount", "pending_review"}
        or case.version != command.expected_case_version
    ):
        raise DomainError("stale_case", 409, "Kasus berubah atau membutuhkan hitungan baru.")
    count = get_stocktake(db, actor, command.stocktake_id)
    if count.id != case.latest_stocktake_id or count.status != "finalized":
        raise DomainError("stale_count", 409, "Gunakan hasil opname terbaru.")
    product = get_product(db, actor, case.product_id)
    balance = balance_for(db, case.business_id, case.product_id)
    if balance.version != count.baseline_version:
        raise RecountRequired(case.id)
    now = db.info.get("now", datetime.now(UTC))
    if command.occurred_at > now or not command.note.strip():
        raise DomainError(
            "invalid_submission", 422, "Catatan wajib diisi dan waktu tidak boleh di masa depan."
        )
    try:
        quantity = parse_quantity(command.quantity, product.step_milli)
    except ValueError as exc:
        raise DomainError("invalid_quantity", 422, str(exc)) from exc
    difference = count.difference_milli
    if command.resolution_kind == "no_movement":
        valid = (
            difference == 0
            and quantity == 0
            and command.movement_kind is None
            and command.cause == "miscount"
        )
    elif command.resolution_kind == "adjustment":
        valid = difference != 0 and quantity == abs(difference) and command.movement_kind is None
    else:
        sign = -1 if command.movement_kind in {"sale", "damage", "supplier_return"} else 1
        valid = bool(command.movement_kind) and quantity > 0 and sign * quantity == difference
    if not valid:
        raise DomainError(
            "invalid_resolution", 422, "Usulan harus menjelaskan seluruh selisih opname terbaru."
        )
    from stokguard.files.schemas import EvidenceTarget
    from stokguard.files.service import get_file, link_evidence

    evidence_ids = sorted({str(file_id) for file_id in command.evidence_ids})
    for file_id in evidence_ids:
        get_file(db, actor, file_id)
    if (
        command.resolution_kind != "no_movement"
        and not evidence_ids
        and not command.missing_evidence_reason.strip()
    ):
        raise DomainError(
            "evidence_required", 422, "Bukti atau penjelasan ketiadaan bukti diperlukan."
        )
    case.version += 1
    item = CaseSubmission(
        business_id=case.business_id,
        case_id=case.id,
        stocktake_id=count.id,
        user_id=str(actor.user_id),
        case_version=case.version,
        cause=command.cause,
        resolution_kind=command.resolution_kind,
        quantity_milli=quantity,
        movement_kind=command.movement_kind,
        occurred_at=command.occurred_at.astimezone(UTC).isoformat(),
        note=command.note.strip(),
        missing_evidence_reason=command.missing_evidence_reason.strip(),
        submitted_at=now.isoformat(),
        snapshot={
            "difference_quantity": format_quantity(difference),
            "balance_version": count.baseline_version,
            "cost_rupiah": str(count.cost_rupiah),
            "evidence_ids": evidence_ids,
            "missing_evidence": command.resolution_kind != "no_movement" and not evidence_ids,
            "priority": product_risk(db, case.business_id, case.product_id, now).model_dump(
                mode="json"
            ),
        },
    )
    db.add(item)
    db.flush()
    db.info["creating_submission_id"] = item.id
    try:
        for file_id in evidence_ids:
            link_evidence(
                db, actor, UUID(file_id), EvidenceTarget(kind="submission", id=UUID(item.id))
            )
    finally:
        db.info.pop("creating_submission_id", None)
    case.current_submission_id = item.id
    case.status, case.updated_at = "pending_review", now.isoformat()
    append_event(
        db,
        actor,
        action="case_submitted",
        entity_type="case",
        entity_id=case_id,
        changes={"submission_id": item.id},
    )
    return submission_view(item)


def decide_case_in_session(
    db: Session, actor: Actor, case_id: UUID, command: DecisionCreate, key: UUID
) -> DecisionView:
    validate_actor(db, actor)
    require_owner(actor)
    case = get_case(db, actor, case_id)
    digest = request_digest({"case_id": str(case_id), **command.model_dump(mode="json")})
    replay = find_replay(db, actor, "decide_case", key, digest)
    if replay:
        return decision_view(db.get(ApprovalDecision, replay))
    if (
        case.status != "pending_review"
        or case.version != command.expected_case_version
        or case.current_submission_id != str(command.submission_id)
    ):
        raise DomainError("stale_submission", 409, "Pengajuan berubah atau sudah diputuskan.")
    submission = db.get(CaseSubmission, str(command.submission_id))
    if (
        submission is None
        or submission.case_id != case.id
        or submission.business_id != case.business_id
    ):
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    if submission.user_id == str(actor.user_id):
        raise DomainError(
            "self_approval", 403, "Pengaju tidak dapat memutuskan pengajuannya sendiri."
        )
    if command.decision != "approve" and not command.note.strip():
        raise DomainError("note_required", 422, "Alasan keputusan wajib diisi.")
    now = db.info.get("now", datetime.now(UTC))
    decision_snapshot = {
        **submission.snapshot,
        "priority": product_risk(db, case.business_id, case.product_id, now).model_dump(
            mode="json"
        ),
    }
    movement_id = None
    if command.decision == "approve":
        count = get_stocktake(db, actor, submission.stocktake_id)
        ensure_no_active_count(db, case.business_id, case.product_id, now)
        balance = balance_for(db, case.business_id, case.product_id)
        if count.id != case.latest_stocktake_id or count.baseline_version != balance.version:
            raise RecountRequired(case.id)
        if submission.resolution_kind != "no_movement":
            kind = submission.movement_kind or (
                "adjustment_out" if count.difference_milli < 0 else "adjustment_in"
            )
            result = book_movement(
                db,
                actor,
                ApprovedMovementCommand(
                    product_id=case.product_id,
                    kind=kind,
                    quantity=format_quantity(submission.quantity_milli),
                    occurred_at=submission.occurred_at,
                    note=submission.note,
                    expected_balance_version=balance.version,
                ),
                source=MovementSource("case", UUID(case.id)),
            )
            movement_id = result.id
        case.status = "resolved"
    else:
        case.status = "rejected" if command.decision == "reject" else "needs_recount"
    case.version += 1
    case.updated_at = now.isoformat()
    item = ApprovalDecision(
        business_id=case.business_id,
        target_type="case",
        target_id=case.id,
        submission_id=submission.id,
        user_id=str(actor.user_id),
        decision=command.decision,
        note=command.note.strip(),
        movement_id=movement_id,
        case_status=case.status,
        decided_at=now.isoformat(),
        snapshot=decision_snapshot,
    )
    db.add(item)
    db.flush()
    append_event(
        db,
        actor,
        action="case_decided",
        entity_type="case",
        entity_id=case_id,
        changes={
            "decision": command.decision,
            "submission_id": submission.id,
            "movement_id": movement_id,
        },
    )
    save_result(db, actor, "decide_case", key, digest, item.id)
    return decision_view(item)


def mark_recount_required(db: Session, actor: Actor, error: RecountRequired):
    case = get_case(db, actor, error.case_id)
    if case.status != "needs_recount":
        case.status = "needs_recount"
        case.current_submission_id = None
        case.version += 1
        case.updated_at = db.info["now"].isoformat()
        append_event(
            db,
            actor,
            action="case_needs_recount",
            entity_type="case",
            entity_id=UUID(case.id),
            changes={"reason": "balance_changed"},
        )


def decide_case(
    engine: Engine, actor: Actor, case_id: UUID, command: DecisionCreate, key: UUID
) -> DecisionView:
    pending = None
    with write_uow(engine) as db:
        db.info["now"] = datetime.now(UTC)
        try:
            result = decide_case_in_session(db, actor, case_id, command, key)
        except RecountRequired as exc:
            mark_recount_required(db, actor, exc)
            pending = exc
    if pending:
        raise pending
    return result


def reversal_view(item: ReversalRequest) -> dict:
    return {
        key: getattr(item, key)
        for key in [
            "id",
            "business_id",
            "original_movement_id",
            "user_id",
            "reason",
            "status",
            "version",
            "created_at",
        ]
    }


def get_reversal(db, actor, request_id):
    item = db.scalar(
        select(ReversalRequest).where(
            ReversalRequest.id == str(request_id),
            ReversalRequest.business_id == str(actor.business_id),
        )
    )
    if item is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return item


def request_reversal(db: Session, actor: Actor, movement_id: UUID, command: ReversalCreate) -> dict:
    original = get_movement(db, actor, movement_id)
    if original.source_type == "reversal" or db.scalar(
        select(ReversalRequest.id).where(
            ReversalRequest.business_id == original.business_id,
            ReversalRequest.original_movement_id == original.id,
        )
    ):
        raise DomainError(
            "reversal_exists",
            409,
            "Transaksi sudah memiliki permintaan pembalikan atau merupakan pembalikan.",
        )
    balance = balance_for(db, original.business_id, original.product_id)
    if balance.version != command.expected_balance_version:
        raise DomainError("stale_balance", 409, "Saldo berubah. Muat ulang data.")
    if not command.reason.strip():
        raise DomainError("reason_required", 422, "Alasan pembalikan wajib diisi.")
    item = ReversalRequest(
        business_id=original.business_id,
        original_movement_id=original.id,
        user_id=str(actor.user_id),
        reason=command.reason.strip(),
        created_at=db.info["now"].isoformat(),
    )
    db.add(item)
    db.flush()
    append_event(
        db,
        actor,
        action="reversal_requested",
        entity_type="reversal_request",
        entity_id=UUID(item.id),
        changes={"original_movement_id": original.id},
    )
    return reversal_view(item)


def decide_reversal(
    db: Session, actor: Actor, request_id: UUID, command: ReversalDecision, key: UUID
) -> DecisionView:
    validate_actor(db, actor)
    require_owner(actor)
    item = get_reversal(db, actor, request_id)
    digest = request_digest({"request_id": str(request_id), **command.model_dump(mode="json")})
    replay = find_replay(db, actor, "decide_reversal", key, digest)
    if replay:
        return decision_view(db.get(ApprovalDecision, replay))
    if item.user_id == str(actor.user_id):
        raise DomainError(
            "self_approval", 403, "Pengaju tidak dapat memutuskan pengajuannya sendiri."
        )
    if item.status != "pending_review" or item.version != command.expected_request_version:
        raise DomainError("stale_request", 409, "Permintaan berubah atau sudah diputuskan.")
    if command.decision == "reject" and not command.note.strip():
        raise DomainError("note_required", 422, "Alasan penolakan wajib diisi.")
    original = get_movement(db, actor, item.original_movement_id)
    now = db.info["now"]
    movement_id = None
    if command.decision == "approve":
        result = book_movement(
            db,
            actor,
            ApprovedMovementCommand(
                product_id=original.product_id,
                kind="adjustment_out" if original.quantity_milli > 0 else "adjustment_in",
                quantity=format_quantity(abs(original.quantity_milli)),
                occurred_at=now,
                note=item.reason,
                expected_balance_version=command.expected_balance_version,
            ),
            source=MovementSource("reversal", UUID(original.id)),
        )
        movement_id = result.id
    item.status = "resolved" if command.decision == "approve" else "rejected"
    item.version += 1
    result = ApprovalDecision(
        business_id=item.business_id,
        target_type="reversal_request",
        target_id=item.id,
        user_id=str(actor.user_id),
        decision=command.decision,
        note=command.note,
        movement_id=movement_id,
        case_status=item.status,
        decided_at=now.isoformat(),
        snapshot={"original_movement_id": original.id, "reason": item.reason},
    )
    db.add(result)
    db.flush()
    append_event(
        db,
        actor,
        action="reversal_decided",
        entity_type="reversal_request",
        entity_id=request_id,
        changes={"decision": command.decision, "movement_id": movement_id},
    )
    save_result(db, actor, "decide_reversal", key, digest, result.id)
    return decision_view(result)
