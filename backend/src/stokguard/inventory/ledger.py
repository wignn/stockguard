from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor, require_owner
from stokguard.auth.models import AuthSession, Membership, User
from stokguard.core.errors import DomainError
from stokguard.core.numbers import checked_integer, format_quantity, parse_quantity
from stokguard.core.transactions import write_uow
from stokguard.inventory.idempotency import find_replay, request_digest, save_result
from stokguard.inventory.models import StockBalance, StockMovement
from stokguard.inventory.schemas import MovementCommand, MovementSource, MovementView
from stokguard.products.service import get_product
from stokguard.stocktakes.service import ensure_no_active_count


def validate_actor(db: Session, actor: Actor) -> None:
    now = db.info.get("now", datetime.now(UTC))
    session = db.get(AuthSession, str(actor.session_id))
    user = db.get(User, str(actor.user_id))
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == str(actor.user_id),
            Membership.business_id == str(actor.business_id),
        )
    )
    if (
        not session
        or session.user_id != str(actor.user_id)
        or session.revoked
        or now >= datetime.fromisoformat(session.expires_at)
        or not user
        or not user.active
    ):
        raise DomainError("invalid_session", 401, "Silakan masuk kembali.")
    if membership is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    if membership.role != actor.role:
        raise DomainError("role_changed", 409, "Peran berubah. Muat ulang sesi.")


def get_movement(db: Session, actor: Actor, movement_id: str | UUID) -> StockMovement:
    item = db.scalar(
        select(StockMovement).where(
            StockMovement.id == str(movement_id),
            StockMovement.business_id == str(actor.business_id),
        )
    )
    if item is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return item


def movement_view(item: StockMovement) -> MovementView:
    return MovementView(
        id=item.id,
        business_id=item.business_id,
        product_id=item.product_id,
        location_id=item.location_id,
        kind=item.kind,
        quantity=format_quantity(item.quantity_milli),
        cost_rupiah=str(item.cost_rupiah),
        balance_quantity=format_quantity(item.balance_after_milli),
        balance_version=item.balance_version,
        occurred_at=item.occurred_at,
        posted_at=item.posted_at,
        note=item.note,
        source_type=item.source_type,
        source_id=item.source_id,
    )


def book_movement(
    db: Session, actor: Actor, command: MovementCommand, *, source: MovementSource
) -> MovementView:
    product = get_product(db, actor, command.product_id)
    if not product.active and source.kind == "manual":
        raise DomainError("product_inactive", 409, "Produk nonaktif tidak menerima transaksi baru.")
    now = db.info.get("now", datetime.now(UTC))
    ensure_no_active_count(db, product.business_id, product.id, now)
    if command.occurred_at > now:
        raise DomainError("future_date", 422, "Waktu transaksi tidak boleh di masa depan.")
    try:
        quantity = parse_quantity(command.quantity, product.step_milli)
        if quantity == 0:
            raise ValueError("Jumlah harus lebih besar dari nol.")
    except ValueError as exc:
        raise DomainError("invalid_quantity", 422, str(exc)) from exc
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.business_id == product.business_id, StockBalance.product_id == product.id
        )
    )
    if balance.version != command.expected_balance_version:
        raise DomainError("stale_version", 409, "Saldo berubah. Muat ulang sebelum mencatat.")
    if command.kind == "opening":
        require_owner(actor)
        if balance.version != 0 or db.scalar(
            select(StockMovement.id)
            .where(
                StockMovement.business_id == product.business_id,
                StockMovement.product_id == product.id,
            )
            .limit(1)
        ):
            raise DomainError(
                "opening_exists",
                409,
                "Stok awal hanya dapat dicatat sekali sebelum transaksi lain.",
            )
    delta = (
        -quantity
        if command.kind in {"sale", "damage", "supplier_return", "adjustment_out"}
        else quantity
    )
    try:
        after = checked_integer(balance.quantity_milli + delta)
    except ValueError as exc:
        raise DomainError("quantity_overflow", 422, "Jumlah melampaui batas penyimpanan.") from exc
    if after < 0:
        raise DomainError("insufficient_stock", 409, "Stok tidak mencukupi untuk transaksi ini.")
    balance.quantity_milli = after
    balance.version += 1
    movement = StockMovement(
        business_id=product.business_id,
        product_id=product.id,
        location_id=balance.location_id,
        kind=command.kind,
        quantity_milli=delta,
        cost_rupiah=product.cost_rupiah,
        balance_after_milli=after,
        balance_version=balance.version,
        user_id=str(actor.user_id),
        occurred_at=command.occurred_at.astimezone(UTC).isoformat(),
        posted_at=now.isoformat(),
        note=command.note,
        source_type=source.kind,
        source_id=str(source.id) if source.id else None,
    )
    db.add(movement)
    db.flush()
    append_event(
        db,
        actor,
        action="movement_booked",
        entity_type="movement",
        entity_id=UUID(movement.id),
        changes={"kind": movement.kind, "quantity": format_quantity(delta), "note": movement.note},
    )
    return movement_view(movement)


def post_in_session(db: Session, actor: Actor, command: MovementCommand, key: UUID) -> MovementView:
    validate_actor(db, actor)
    digest = request_digest(command.model_dump(mode="json"))
    replay = find_replay(db, actor, "post_movement", key, digest)
    if replay:
        return movement_view(get_movement(db, actor, replay))
    result = book_movement(db, actor, command, source=MovementSource())
    save_result(db, actor, "post_movement", key, digest, result.id)
    return result


def post_movement(
    engine: Engine, actor: Actor, command: MovementCommand, key: UUID
) -> MovementView:
    with write_uow(engine) as db:
        return post_in_session(db, actor, command, key)
