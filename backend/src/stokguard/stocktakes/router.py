from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.transactions import write_uow
from stokguard.stocktakes.models import Stocktake
from stokguard.stocktakes.schemas import (
    CountAction,
    CountFinalize,
    CountStart,
    StocktakeResult,
    StocktakeView,
)
from stokguard.stocktakes.service import (
    act_on_count,
    finalize_stocktake,
    get_stocktake,
    start_stocktake,
    stocktake_view,
)

router = APIRouter(prefix="/api/v1/businesses/{business_id}/stocktakes", tags=["stocktakes"])


def prepare(db, request, business_id):
    actor = actor_in_session(request, db, business_id)
    db.info.update(now=request.app.state.clock.now(), request_id=request.state.request_id)
    return actor


@router.post("", status_code=201, response_model=StocktakeView)
def start(business_id: UUID, payload: CountStart, request: Request):
    with write_uow(request.app.state.engine) as db:
        return start_stocktake(db, prepare(db, request, business_id), payload.product_id)


@router.get("")
def history(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        filters = [Stocktake.business_id == str(business_id)]
        total = db.scalar(select(func.count()).select_from(Stocktake).where(*filters))
        rows = db.scalars(
            select(Stocktake)
            .where(*filters)
            .order_by(Stocktake.started_at.desc(), Stocktake.id)
            .offset(offset)
            .limit(limit)
        )
        return {
            "items": [stocktake_view(db, item) for item in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }


@router.get("/{count_id}", response_model=StocktakeView)
def detail(business_id: UUID, count_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        return stocktake_view(db, get_stocktake(db, actor, count_id))


@router.post("/{count_id}/finalize", response_model=StocktakeResult)
def finalize(business_id: UUID, count_id: UUID, payload: CountFinalize, request: Request):
    with write_uow(request.app.state.engine) as db:
        return finalize_stocktake(db, prepare(db, request, business_id), count_id, payload)


@router.post("/{count_id}/extend", response_model=StocktakeView)
def extend(business_id: UUID, count_id: UUID, payload: CountAction, request: Request):
    with write_uow(request.app.state.engine) as db:
        return act_on_count(db, prepare(db, request, business_id), count_id, payload, "extend")


@router.post("/{count_id}/cancel", response_model=StocktakeView)
def cancel(business_id: UUID, count_id: UUID, payload: CountAction, request: Request):
    with write_uow(request.app.state.engine) as db:
        return act_on_count(db, prepare(db, request, business_id), count_id, payload, "cancel")
