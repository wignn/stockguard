from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.audit.service import append_event
from stokguard.auth.dependencies import Actor, require_owner
from stokguard.businesses.models import Location
from stokguard.core.errors import DomainError
from stokguard.core.numbers import format_quantity, parse_quantity, parse_rupiah
from stokguard.inventory.models import StockBalance, StockMovement
from stokguard.products.models import Product
from stokguard.products.schemas import ProductCreate, ProductPatch, ProductView


def get_product(db: Session, actor: Actor, product_id: UUID | str) -> Product:
    product = db.scalar(
        select(Product).where(
            Product.id == str(product_id), Product.business_id == str(actor.business_id)
        )
    )
    if product is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return product


def product_view(db: Session, product: Product) -> ProductView:
    balance = db.scalar(
        select(StockBalance).where(
            StockBalance.business_id == product.business_id, StockBalance.product_id == product.id
        )
    )
    return ProductView(
        id=product.id,
        business_id=product.business_id,
        sku=product.sku,
        name=product.name,
        unit=product.unit,
        step_quantity=format_quantity(product.step_milli),
        cost_rupiah=str(product.cost_rupiah),
        active=product.active,
        version=product.version,
        balance_quantity=format_quantity(balance.quantity_milli),
        balance_version=balance.version,
    )


def ensure_sku_available(db: Session, actor: Actor, sku: str, product_id=None) -> None:
    query = select(Product.id).where(
        Product.business_id == str(actor.business_id), Product.sku == sku
    )
    if product_id:
        query = query.where(Product.id != product_id)
    if db.scalar(query):
        raise DomainError("sku_exists", 409, "SKU sudah digunakan di usaha ini.")


def create_product(db: Session, actor: Actor, command: ProductCreate) -> ProductView:
    require_owner(actor)
    ensure_sku_available(db, actor, command.sku)
    product = Product(
        business_id=str(actor.business_id),
        sku=command.sku,
        name=command.name,
        unit=command.unit,
        step_milli=parse_quantity(command.step_quantity, 1),
        cost_rupiah=parse_rupiah(command.cost_rupiah),
    )
    db.add(product)
    db.flush()
    location = db.scalar(select(Location).where(Location.business_id == str(actor.business_id)))
    db.add(
        StockBalance(
            business_id=product.business_id, product_id=product.id, location_id=location.id
        )
    )
    db.flush()
    append_event(
        db,
        actor,
        action="product_created",
        entity_type="product",
        entity_id=UUID(product.id),
        changes={"sku": product.sku},
    )
    return product_view(db, product)


def patch_product(
    db: Session, actor: Actor, product_id: UUID, command: ProductPatch
) -> ProductView:
    require_owner(actor)
    product = get_product(db, actor, product_id)
    if product.version != command.expected_version:
        raise DomainError("stale_version", 409, "Data berubah. Muat ulang sebelum menyimpan.")
    changes = command.model_dump(exclude_unset=True, exclude={"expected_version"})
    values = {
        "sku": product.sku,
        "name": product.name,
        "unit": product.unit,
        "step_quantity": format_quantity(product.step_milli),
        "cost_rupiah": str(product.cost_rupiah),
    }
    validated = ProductCreate.model_validate(
        values | {k: v for k, v in changes.items() if k != "active"}
    )
    step = parse_quantity(validated.step_quantity, 1)
    if (validated.unit != product.unit or step != product.step_milli) and db.scalar(
        select(StockMovement.id)
        .where(
            StockMovement.business_id == product.business_id, StockMovement.product_id == product.id
        )
        .limit(1)
    ):
        raise DomainError("unit_locked", 409, "Satuan tidak dapat diubah setelah ada transaksi.")
    ensure_sku_available(db, actor, validated.sku, product.id)
    product.sku, product.name, product.unit = validated.sku, validated.name, validated.unit
    product.step_milli, product.cost_rupiah = step, parse_rupiah(validated.cost_rupiah)
    if "active" in changes:
        if changes["active"] is None:
            raise DomainError("validation_error", 422, "Status produk tidak valid.")
        product.active = changes["active"]
    product.version += 1
    append_event(
        db,
        actor,
        action="product_updated",
        entity_type="product",
        entity_id=product_id,
        changes=changes,
    )
    db.flush()
    return product_view(db, product)
