from uuid import UUID

from fastapi import APIRouter, Request
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import actor_in_session
from stokguard.businesses.models import Business

router = APIRouter(prefix="/api/v1/businesses", tags=["businesses"])


@router.get("/{business_id}")
def business_detail(business_id: UUID, request: Request):
    with Session(request.app.state.engine) as db:
        actor_in_session(request, db, business_id)
        business = db.get(Business, str(business_id))
        return {
            "id": business.id,
            "name": business.name,
            "timezone": business.timezone,
            "is_demo": business.is_demo,
        }
