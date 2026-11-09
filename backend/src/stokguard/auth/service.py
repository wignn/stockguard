from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.audit.models import AuditEvent
from stokguard.auth.models import Membership, User
from stokguard.auth.passwords import hash_password
from stokguard.businesses.models import Business, Location
from stokguard.core.errors import DomainError


def add_user(
    db: Session, business_id: UUID | str, username: str, password: str, role: str, now: datetime
) -> User:
    if role not in {"owner", "staff"}:
        raise ValueError("Peran tidak valid.")
    username = username.strip().casefold()
    if not username or len(username) > 100:
        raise ValueError("Username harus terdiri dari 1 hingga 100 karakter.")
    if db.scalar(select(User).where(User.username == username)):
        raise DomainError("username_exists", 409, "Username sudah digunakan.")
    user = User(username=username, password_hash=hash_password(password))
    db.add(user)
    db.flush()
    db.add(Membership(user_id=user.id, business_id=str(business_id), role=role))
    db.add(
        AuditEvent(
            business_id=str(business_id),
            user_id=user.id,
            action="account_created",
            entity_type="user",
            entity_id=user.id,
            occurred_at=now.isoformat(),
            changes={"role": role},
            request_id=None,
        )
    )
    db.flush()
    return user


def record_user_event(
    db: Session,
    user: User,
    action: str,
    now: datetime,
    *,
    source: str,
    request_id: str | None = None,
) -> None:
    for membership in db.scalars(select(Membership).where(Membership.user_id == user.id)):
        db.add(
            AuditEvent(
                business_id=membership.business_id,
                user_id=user.id,
                action=action,
                entity_type="user",
                entity_id=user.id,
                occurred_at=now.isoformat(),
                changes={"source": source},
                request_id=request_id,
            )
        )
    db.flush()


def setup_business(
    db: Session, name: str, username: str, password: str, now: datetime
) -> tuple[Business, User]:
    if not name.strip() or len(name) > 200:
        raise ValueError("Nama usaha harus terdiri dari 1 hingga 200 karakter.")
    business = Business(name=name.strip())
    db.add(business)
    db.flush()
    db.add(Location(business_id=business.id))
    owner = add_user(db, business.id, username, password, "owner", now)
    return business, owner
