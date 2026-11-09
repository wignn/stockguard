from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal, localcontext
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor
from stokguard.core.errors import DomainError
from stokguard.core.numbers import format_quantity, parse_quantity
from stokguard.inventory.models import StockBalance
from stokguard.investigations.models import InvestigationCase
from stokguard.products.service import get_product
from stokguard.stocktakes.models import Stocktake
from stokguard.stocktakes.schemas import CountAction, CountFinalize, StocktakeResult, StocktakeView


def expire_counts(db: Session, business_id: str, now: datetime) -> None:
    for count in db.scalars(
        select(Stocktake).where(Stocktake.business_id == business_id, Stocktake.status == "active")
    ):
        if now >= datetime.fromisoformat(count.expires_at):
            count.status = "expired"
            count.version += 1
    db.flush()


def ensure_no_active_count(db: Session, business_id: str, product_id: str, now: datetime) -> None:
    expire_counts(db, business_id, now)
    if db.scalar(
        select(Stocktake.id).where(
            Stocktake.business_id == business_id,
            Stocktake.product_id == product_id,
            Stocktake.status == "active",
        )
    ):
        raise DomainError(
            "active_stocktake",
            409,
            "Produk sedang dihitung. Selesaikan atau batalkan opname terlebih dahulu.",
        )


def get_stocktake(db: Session, actor: Actor, count_id: UUID | str) -> Stocktake:
    count = db.scalar(
        select(Stocktake).where(
            Stocktake.id == str(count_id), Stocktake.business_id == str(actor.business_id)
        )
    )
    if count is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return count


def stocktake_view(db: Session, count: Stocktake) -> StocktakeView:
    case_id = db.scalar(
        select(InvestigationCase.id).where(
            InvestigationCase.business_id == count.business_id,
            (InvestigationCase.initial_stocktake_id == count.id)
            | (InvestigationCase.latest_stocktake_id == count.id),
        )
    )
    percentage = None
    if count.baseline_milli and count.difference_milli is not None:
        with localcontext() as context:
            context.prec = 50
            percentage = str(
                (Decimal(count.difference_milli) * 100 / count.baseline_milli).quantize(
                    Decimal("0.01"), rounding=ROUND_HALF_UP
                )
            )
    return StocktakeView(
        id=count.id,
        business_id=count.business_id,
        product_id=count.product_id,
        location_id=count.location_id,
        user_id=count.user_id,
        status=count.status,
        version=count.version,
        baseline_quantity=format_quantity(count.baseline_milli),
        baseline_version=count.baseline_version,
        counted_quantity=format_quantity(count.counted_milli)
        if count.counted_milli is not None
        else None,
        difference_quantity=format_quantity(count.difference_milli)
        if count.difference_milli is not None
        else None,
        difference_percentage=percentage,
        started_at=count.started_at,
        expires_at=count.expires_at,
        finalized_at=count.finalized_at,
        case_id=case_id,
    )


def start_stocktake(db: Session, actor: Actor, product_id: UUID) -> StocktakeView:
    now = db.info.get("now", datetime.now(UTC))
    product = get_product(db, actor, product_id)
    ensure_no_active_count(db, product.business_id, product.id, now)
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.business_id == product.business_id, StockBalance.product_id == product.id
        )
    )
    count = Stocktake(
        business_id=product.business_id,
        product_id=product.id,
        location_id=balance.location_id,
        user_id=str(actor.user_id),
        baseline_milli=balance.quantity_milli,
        baseline_version=balance.version,
        cost_rupiah=product.cost_rupiah,
        started_at=now.isoformat(),
        expires_at=(now + timedelta(minutes=15)).isoformat(),
    )
    db.add(count)
    db.flush()
    append_event(
        db,
        actor,
        action="stocktake_started",
        entity_type="stocktake",
        entity_id=UUID(count.id),
        changes={"baseline_version": count.baseline_version},
    )
    return stocktake_view(db, count)


def require_active_holder(count: Stocktake, actor: Actor, expected_version: int, now: datetime):
    if (
        count.status != "active"
        or now >= datetime.fromisoformat(count.expires_at)
        or count.version != expected_version
    ):
        raise DomainError(
            "stale_stocktake", 409, "Sesi hitung berubah atau kedaluwarsa. Mulai hitungan baru."
        )
    if count.user_id != str(actor.user_id):
        raise DomainError(
            "count_holder_required", 403, "Hanya pemegang sesi yang dapat menyelesaikan hitungan."
        )


def finalize_stocktake(
    db: Session, actor: Actor, stocktake_id: UUID, command: CountFinalize
) -> StocktakeResult:
    now = db.info.get("now", datetime.now(UTC))
    expire_counts(db, str(actor.business_id), now)
    count = get_stocktake(db, actor, stocktake_id)
    require_active_holder(count, actor, command.expected_version, now)
    product = get_product(db, actor, count.product_id)
    try:
        quantity = parse_quantity(command.counted_quantity, product.step_milli)
    except ValueError as exc:
        raise DomainError("invalid_quantity", 422, str(exc)) from exc
    difference = quantity - count.baseline_milli
    if not command.no_physical_movement or (
        difference and not all([command.recounted, command.rack_checked, command.storage_checked])
    ):
        raise DomainError(
            "count_confirmation_required",
            422,
            "Konfirmasi pergerakan fisik dan pemeriksaan selisih diperlukan.",
        )
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.business_id == count.business_id,
            StockBalance.product_id == count.product_id,
        )
    )
    if balance.version != count.baseline_version:
        raise DomainError("stale_balance", 409, "Saldo berubah. Hitung ulang diperlukan.")
    count.counted_milli, count.difference_milli = quantity, difference
    count.status, count.finalized_at = "finalized", now.isoformat()
    count.version += 1
    for field in ["recounted", "rack_checked", "storage_checked", "no_physical_movement"]:
        setattr(count, field, getattr(command, field))
    case = db.scalar(
        select(InvestigationCase).where(
            InvestigationCase.business_id == count.business_id,
            InvestigationCase.product_id == count.product_id,
            InvestigationCase.status != "resolved",
        )
    )
    if case:
        case.latest_stocktake_id = count.id
        case.difference_milli, case.cost_rupiah = difference, count.cost_rupiah
        case.version += 1
        case.current_submission_id = None
        case.status, case.updated_at = "investigating", now.isoformat()
    elif difference:
        db.add(
            InvestigationCase(
                business_id=count.business_id,
                product_id=count.product_id,
                location_id=count.location_id,
                initial_stocktake_id=count.id,
                latest_stocktake_id=count.id,
                difference_milli=difference,
                cost_rupiah=count.cost_rupiah,
                created_at=now.isoformat(),
                updated_at=now.isoformat(),
            )
        )
    db.flush()
    append_event(
        db,
        actor,
        action="stocktake_finalized",
        entity_type="stocktake",
        entity_id=stocktake_id,
        changes={"difference_quantity": format_quantity(difference)},
    )
    return StocktakeResult(**stocktake_view(db, count).model_dump())


def act_on_count(
    db: Session, actor: Actor, count_id: UUID, command: CountAction, action: str
) -> StocktakeView:
    now = db.info["now"]
    expire_counts(db, str(actor.business_id), now)
    count = get_stocktake(db, actor, count_id)
    if action == "cancel" and actor.role == "owner" and count.user_id != str(actor.user_id):
        if not command.note.strip():
            raise DomainError("note_required", 422, "Alasan pembatalan wajib diisi.")
        if count.status != "active" or count.version != command.expected_version:
            raise DomainError("stale_stocktake", 409, "Sesi hitung telah berubah.")
    else:
        require_active_holder(count, actor, command.expected_version, now)
    count.version += 1
    count.note = command.note
    if action == "cancel":
        count.status = "cancelled"
    else:
        count.expires_at = (now + timedelta(minutes=15)).isoformat()
    append_event(
        db,
        actor,
        action=f"stocktake_{action}",
        entity_type="stocktake",
        entity_id=count_id,
        changes={"note": command.note},
    )
    return stocktake_view(db, count)
