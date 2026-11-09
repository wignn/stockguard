from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Query, Request
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.core.numbers import value_delta
from stokguard.investigations.models import InvestigationCase
from stokguard.products.models import Product
from stokguard.products.service import get_product, product_view
from stokguard.risk.schemas import RiskAssessment
from stokguard.risk.service import product_risk

router = APIRouter(prefix="/api/v1/businesses/{business_id}", tags=["priorities"])


@router.get("/products/{product_id}/risk", response_model=RiskAssessment)
def risk(business_id: UUID, product_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        actor = actor_in_session(request, db, business_id)
        get_product(db, actor, product_id)
        return product_risk(db, str(business_id), str(product_id), request.app.state.clock.now())


@router.get("/dashboard")
def dashboard(
    business_id: UUID,
    request: Request,
    offset: int = Query(0, ge=0),
    limit: int = Query(25, ge=1, le=100),
    q: str = Query("", max_length=200),
    priority: Literal["high", "medium", "low", "insufficient"] | None = None,
):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        now = request.app.state.clock.now()
        products = db.scalars(
            select(Product).where(Product.business_id == str(business_id), Product.active.is_(True))
        ).all()
        ranks = {"high": 0, "medium": 1, "low": 2, "insufficient": 3}
        rows = []
        high = 0
        for product in products:
            assessment = product_risk(db, str(business_id), product.id, now)
            high += assessment.priority == "high"
            if priority and priority != assessment.priority:
                continue
            if (
                q
                and q.casefold() not in product.name.casefold()
                and q.casefold() not in product.sku.casefold()
            ):
                continue
            cases = db.scalars(
                select(InvestigationCase).where(
                    InvestigationCase.business_id == str(business_id),
                    InvestigationCase.product_id == product.id,
                    InvestigationCase.status != "resolved",
                )
            ).all()
            amount = max(
                (abs(value_delta(c.difference_milli, c.cost_rupiah)) for c in cases), default=0
            )
            oldest = min((c.created_at for c in cases), default="9999")
            rows.append(
                (
                    ranks[assessment.priority],
                    -amount,
                    oldest,
                    product.sku,
                    {"product": product_view(db, product), "risk": assessment},
                )
            )
        rows.sort(key=lambda item: item[:4])
        unresolved = db.scalar(
            select(func.count())
            .select_from(InvestigationCase)
            .where(
                InvestigationCase.business_id == str(business_id),
                InvestigationCase.status != "resolved",
            )
        )
        return {
            "active_products": len(products),
            "unresolved_cases": unresolved,
            "high_priority_products": high,
            "population": "active_products",
            "products": {
                "items": [row[4] for row in rows[offset : offset + limit]],
                "total": len(rows),
                "offset": offset,
                "limit": limit,
            },
        }
