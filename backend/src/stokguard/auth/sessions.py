import secrets
from datetime import datetime, timedelta
from threading import Lock

from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import token_digest
from stokguard.auth.models import AuthSession, Membership, User
from stokguard.businesses.models import Business
from stokguard.core.errors import DomainError


class LoginLimiter:
    def __init__(self):
        self._failures: dict[tuple[str, str], list[datetime]] = {}
        self._lock = Lock()

    def check(self, username: str, ip: str, now: datetime) -> None:
        with self._lock:
            cutoff = now - timedelta(minutes=15)
            self._failures = {
                key: [stamp for stamp in values if stamp > cutoff]
                for key, values in self._failures.items()
                if any(stamp > cutoff for stamp in values)
            }
            if (
                len(self._failures.get(("user", username), [])) >= 5
                or len(self._failures.get(("ip", ip), [])) >= 20
            ):
                raise DomainError(
                    "login_limited", 429, "Terlalu banyak percobaan. Coba lagi nanti."
                )

    def failed(self, username: str, ip: str, now: datetime) -> None:
        with self._lock:
            for key in [("user", username), ("ip", ip)]:
                self._failures.setdefault(key, []).append(now)


def issue_session(db: Session, user: User, now: datetime) -> tuple[AuthSession, str]:
    token = secrets.token_urlsafe(32)
    session = AuthSession(
        user_id=user.id,
        token_hash=token_digest(token),
        csrf_token=secrets.token_urlsafe(32),
        issued_at=now.isoformat(),
        expires_at=(now + timedelta(days=7)).isoformat(),
    )
    db.add(session)
    db.flush()
    return session, token


def membership_views(db: Session, user: User) -> list[dict]:
    rows = db.execute(
        select(Membership, Business)
        .join(Business, Membership.business_id == Business.id)
        .where(Membership.user_id == user.id)
    ).all()
    return [
        {
            "business_id": business.id,
            "name": business.name,
            "role": membership.role,
            "timezone": business.timezone,
            "is_demo": business.is_demo,
        }
        for membership, business in rows
    ]


def session_view(db: Session, session: AuthSession, user: User) -> dict:
    return {
        "user": {"id": user.id, "username": user.username},
        "expires_at": session.expires_at,
        "csrf_token": session.csrf_token,
        "memberships": membership_views(db, user),
    }
