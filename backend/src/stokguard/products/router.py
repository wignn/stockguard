from uuid import UUID

from fastapi import APIRouter, Query, Request
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.errors import DomainError
from stokguard.core.transactions import write_uow
from stokguard.products.models import Product
from stokguard.products.schemas import ProductCreate, ProductPatch, ProductView
from stokguard.products.service import create_product, get_product, patch_product, product_view

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["products"])


@router.post("/products", status_code=201, response_model=ProductView)
def create(business_id: UUID, payload: ProductCreate, request: Request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        return create_product(db, actor, payload)


@router.get("/balances")
@router.get("/products")
def list_products(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=200),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        filters = [Product.business_id == str(business_id)]
        if q:
            filters.append(
                Product.name.contains(q, autoescape=True)
                | Product.sku.contains(q.upper(), autoescape=True)
            )
        total = db.scalar(select(func.count()).select_from(Product).where(*filters))
        products = db.scalars(
            select(Product)
            .where(*filters)
            .order_by(Product.sku, Product.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [product_view(db, item) for item in products],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.get("/products/{product_id}", response_model=ProductView)
def detail(business_id: UUID, product_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        return product_view(db, get_product(db, actor, product_id))


@router.patch("/products/{product_id}", response_model=ProductView)
def patch(business_id: UUID, product_id: UUID, payload: ProductPatch, request: Request):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        try:
            return patch_product(db, actor, product_id, payload)
        except ValidationError as exc:
            raise DomainError("validation_error", 422, "Periksa isian produk.") from exc
