from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.inventory.ledger import get_movement, movement_view, post_in_session
from stokguard.inventory.models import StockMovement
from stokguard.inventory.schemas import MovementCommand, MovementView
from stokguard.products.service import get_product

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["inventory"])


@router.post("/movements", status_code=201, response_model=MovementView)
def create(
    business_id: UUID,
    payload: MovementCommand,
    request: Request,
    idempotency_key: Annotated[UUID, Header(alias="Idempotency-Key")],
):
    with write_uow(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
        return post_in_session(db, actor, payload, idempotency_key)


def movement_page(db, business_id, offset, limit, product_id=None):
    filters = [StockMovement.business_id == str(business_id)]
    if product_id:
        filters.append(StockMovement.product_id == str(product_id))
    total = db.scalar(select(func.count()).select_from(StockMovement).where(*filters))
    rows = db.scalars(
        select(StockMovement)
        .where(*filters)
        .order_by(
            StockMovement.posted_at.desc(), StockMovement.balance_version.desc(), StockMovement.id
        )
        .offset(offset)
        .limit(limit)
    )
    return {
        "items": [movement_view(item) for item in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


@router.get("/movements")
def history(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        return movement_page(db, business_id, offset, limit)


@router.get("/movements/{movement_id}", response_model=MovementView)
def detail(business_id: UUID, movement_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        return movement_view(get_movement(db, actor, movement_id))


@router.get("/products/{product_id}/timeline")
def timeline(
    business_id: UUID,
    product_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        get_product(db, actor, product_id)
        return movement_page(db, business_id, offset, limit, product_id)
