from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor
from stokguard.core.errors import DomainError
from stokguard.core.numbers import parse_quantity, parse_rupiah
from stokguard.core.transactions import write_uow
from stokguard.drafts.models import DraftLine, TransactionDraft
from stokguard.drafts.schemas import DraftConfirm, DraftCreate, DraftPatch, LinePatch
from stokguard.files.schemas import EvidenceTarget
from stokguard.files.service import get_file, link_evidence
from stokguard.inventory.idempotency import find_replay, request_digest, save_result
from stokguard.inventory.ledger import book_movement, get_movement, movement_view, validate_actor
from stokguard.inventory.schemas import MovementCommand, MovementSource, MovementView
from stokguard.products.service import get_product


def get_draft(db: Session, actor: Actor, draft_id: UUID | str) -> TransactionDraft:
    item = db.scalar(
        select(TransactionDraft).where(
            TransactionDraft.id == str(draft_id),
            TransactionDraft.business_id == str(actor.business_id),
        )
    )
    if item is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return item


def get_line(db, draft, line_id):
    line = db.scalar(
        select(DraftLine).where(DraftLine.draft_id == draft.id, DraftLine.id == str(line_id))
    )
    if line is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return line


def line_view(line: DraftLine) -> dict:
    return {
        key: getattr(line, key)
        for key in [
            "id",
            "position",
            "suggestion",
            "product_id",
            "kind",
            "quantity",
            "unit_price_rupiah",
            "occurred_at",
            "note",
            "status",
            "version",
            "movement_id",
        ]
    }


def draft_view(db, draft) -> dict:
    lines = db.scalars(
        select(DraftLine).where(DraftLine.draft_id == draft.id).order_by(DraftLine.position)
    ).all()
    confirmed = sum(line.status == "confirmed" for line in lines)
    duplicates = (
        db.scalars(
            select(TransactionDraft.id)
            .where(
                TransactionDraft.business_id == draft.business_id,
                TransactionDraft.receipt_number == draft.receipt_number,
                TransactionDraft.id != draft.id,
            )
            .order_by(TransactionDraft.created_at, TransactionDraft.id)
        ).all()
        if draft.receipt_number
        else []
    )
    return {
        "id": draft.id,
        "file_id": draft.file_id,
        "ocr_job_id": draft.ocr_job_id,
        "receipt_number": draft.receipt_number,
        "receipt_date": draft.receipt_date,
        "original_ocr": draft.original_ocr,
        "version": draft.version,
        "created_at": draft.created_at,
        "status": "confirmed" if confirmed == len(lines) else "partial" if confirmed else "pending",
        "duplicate_ids": list(duplicates),
        "lines": [line_view(line) for line in lines],
    }


def validate_values(db, actor, values):
    if values.get("product_id"):
        get_product(db, actor, values["product_id"])
    try:
        if values.get("quantity") is not None:
            parse_quantity(values["quantity"], 1)
        if values.get("unit_price_rupiah") is not None:
            parse_rupiah(values["unit_price_rupiah"])
    except ValueError as exc:
        raise DomainError("invalid_amount", 422, str(exc)) from exc


def create_draft(db: Session, actor: Actor, command: DraftCreate) -> dict:
    get_file(db, actor, command.file_id)
    draft = TransactionDraft(
        business_id=str(actor.business_id),
        file_id=str(command.file_id),
        user_id=str(actor.user_id),
        receipt_number=(command.receipt_number or "").strip() or None,
        receipt_date=command.receipt_date.isoformat() if command.receipt_date else None,
        created_at=db.info["now"].isoformat(),
    )
    db.add(draft)
    db.flush()
    for position, payload in enumerate(command.lines):
        values = payload.model_dump(mode="json")
        validate_values(db, actor, values)
        db.add(DraftLine(draft_id=draft.id, position=position, **values))
    db.flush()
    append_event(
        db,
        actor,
        action="draft_created",
        entity_type="draft",
        entity_id=UUID(draft.id),
        changes={"file_id": draft.file_id},
    )
    return draft_view(db, draft)


def patch_draft(db, actor, draft_id, command: DraftPatch):
    draft = get_draft(db, actor, draft_id)
    if draft.version != command.expected_version:
        raise DomainError("stale_draft", 409, "Draf berubah. Muat ulang data.")
    if db.scalar(
        select(DraftLine.id)
        .where(DraftLine.draft_id == draft.id, DraftLine.status == "confirmed")
        .limit(1)
    ):
        raise DomainError("draft_booked", 409, "Draf yang sudah dibukukan tidak dapat diubah.")
    for key, value in command.model_dump(mode="json", exclude_unset=True).items():
        if key != "expected_version":
            setattr(draft, key, value.strip() or None if isinstance(value, str) else value)
    draft.version += 1
    append_event(
        db,
        actor,
        action="draft_updated",
        entity_type="draft",
        entity_id=UUID(draft.id),
        changes={"version": draft.version},
    )
    return draft_view(db, draft)


def patch_line(db, actor, draft_id, line_id, command: LinePatch):
    draft = get_draft(db, actor, draft_id)
    line = get_line(db, draft, line_id)
    if line.status != "pending" or line.version != command.expected_version:
        raise DomainError("stale_line", 409, "Baris berubah atau sudah dibukukan.")
    values = command.model_dump(mode="json", exclude_unset=True, exclude={"expected_version"})
    validate_values(db, actor, values)
    for key, value in values.items():
        setattr(line, key, value)
    line.version += 1
    draft.version += 1
    db.flush()
    append_event(
        db,
        actor,
        action="draft_line_updated",
        entity_type="draft_line",
        entity_id=UUID(line.id),
        changes={"version": line.version},
    )
    return line_view(line)


def confirm_in_session(db, actor, draft_id, line_id, command: DraftConfirm, key):
    validate_actor(db, actor)
    draft = get_draft(db, actor, draft_id)
    line = get_line(db, draft, line_id)
    digest = request_digest(
        {"draft_id": str(draft_id), "line_id": str(line_id), **command.model_dump(mode="json")}
    )
    replay = find_replay(db, actor, "confirm_draft_line", key, digest)
    if replay:
        return movement_view(get_movement(db, actor, replay))
    if line.status != "pending" or line.version != command.expected_line_version:
        raise DomainError("stale_line", 409, "Baris berubah atau sudah dibukukan.")
    if not command.reviewed or not all(
        [line.product_id, line.kind, line.quantity, line.occurred_at]
    ):
        raise DomainError(
            "review_required", 422, "Periksa produk, jenis, jumlah, dan waktu transaksi."
        )
    product = get_product(db, actor, line.product_id)
    if not product.active:
        raise DomainError("product_inactive", 409, "Produk nonaktif tidak menerima transaksi baru.")
    result = book_movement(
        db,
        actor,
        MovementCommand(
            product_id=line.product_id,
            kind=line.kind,
            quantity=line.quantity,
            occurred_at=line.occurred_at,
            note=line.note,
            expected_balance_version=command.expected_balance_version,
        ),
        source=MovementSource("draft_line", UUID(line.id)),
    )
    link_evidence(db, actor, UUID(draft.file_id), EvidenceTarget(kind="movement", id=result.id))
    line.status, line.movement_id = "confirmed", str(result.id)
    line.version += 1
    draft.version += 1
    append_event(
        db,
        actor,
        action="draft_line_confirmed",
        entity_type="draft_line",
        entity_id=UUID(line.id),
        changes={"movement_id": str(result.id), "reviewed": True},
    )
    save_result(db, actor, "confirm_draft_line", key, digest, str(result.id))
    return result


def confirm_draft_line(
    engine: Engine,
    actor: Actor,
    draft_id: UUID,
    line_id: UUID,
    command: DraftConfirm,
    key: UUID,
    *,
    now: datetime | None = None,
) -> MovementView:
    with write_uow(engine) as db:
        db.info["now"] = now or datetime.now(UTC)
        return confirm_in_session(db, actor, draft_id, line_id, command, key)


def create_from_ocr(db, job, result):
    if db.scalar(select(TransactionDraft.id).where(TransactionDraft.ocr_job_id == job.id)):
        return
    draft = TransactionDraft(
        business_id=job.business_id,
        file_id=job.file_id,
        ocr_job_id=job.id,
        user_id=job.user_id,
        original_ocr=result.model_dump(mode="json"),
        receipt_number=result.receipt_number,
        receipt_date=result.receipt_date,
        created_at=db.info.get("now", datetime.now(UTC)).isoformat(),
    )
    db.add(draft)
    db.flush()
    for position, suggestion in enumerate(result.lines[:100] or [None]):
        db.add(
            DraftLine(
                draft_id=draft.id,
                position=position,
                suggestion=suggestion.model_dump(mode="json") if suggestion else None,
            )
        )
    db.flush()
