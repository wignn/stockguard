import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime
from typing import Literal
from uuid import UUID

from fastapi import Request
from sqlalchemy import select
from sqlalchemy.orm import Session

from stokguard.auth.models import AuthSession, Membership, User
from stokguard.core.errors import DomainError

COOKIE = "stokguard_session"


@dataclass(frozen=True)
class Actor:
    user_id: UUID
    business_id: UUID
    role: Literal["owner", "staff"]
    session_id: UUID


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_origin(request: Request) -> None:
    if request.headers.get("origin") not in request.app.state.settings.allowed_origins:
        raise DomainError("origin_denied", 403, "Asal permintaan tidak diizinkan.")


def require_session(request: Request, db: Session) -> tuple[AuthSession, User]:
    cookie = request.cookies.get(COOKIE)
    authorization = request.headers.get("authorization")
    if cookie and authorization:
        raise DomainError("ambiguous_credentials", 401, "Gunakan satu metode autentikasi.")
    if authorization:
        loopback = request.url.hostname in {"localhost", "127.0.0.1", "::1", "testserver"}
        if request.url.scheme != "https" and (
            request.app.state.settings.secure_cookies or not loopback
        ):
            raise DomainError("https_required", 403, "Koneksi HTTPS diperlukan.")
        scheme, _, token = authorization.partition(" ")
        if scheme.lower() != "bearer" or not token:
            raise DomainError("invalid_session", 401, "Silakan masuk kembali.")
    else:
        token = cookie
    if not token or len(token) > 200:
        raise DomainError("invalid_session", 401, "Silakan masuk kembali.")
    session = db.scalar(select(AuthSession).where(AuthSession.token_hash == token_digest(token)))
    if (
        session is None
        or session.revoked
        or request.app.state.clock.now() >= datetime.fromisoformat(session.expires_at)
    ):
        raise DomainError("invalid_session", 401, "Silakan masuk kembali.")
    user = db.get(User, session.user_id)
    if user is None or not user.active:
        raise DomainError("invalid_session", 401, "Silakan masuk kembali.")
    if cookie and request.method not in {"GET", "HEAD", "OPTIONS"}:
        check_origin(request)
        if not secrets.compare_digest(request.headers.get("x-csrf-token", ""), session.csrf_token):
            raise DomainError("csrf_denied", 403, "Sesi formulir tidak valid. Muat ulang halaman.")
    return session, user


def actor_in_session(request: Request, db: Session, business_id: UUID) -> Actor:
    session, user = require_session(request, db)
    membership = db.scalar(
        select(Membership).where(
            Membership.user_id == user.id, Membership.business_id == str(business_id)
        )
    )
    if membership is None:
        raise DomainError("not_found", 404, "Data tidak ditemukan.")
    return Actor(UUID(user.id), business_id, membership.role, UUID(session.id))


def require_actor(request: Request, business_id: UUID) -> Actor:
    with Session(request.app.state.engine) as db:
        return actor_in_session(request, db, business_id)


def require_owner(actor: Actor) -> None:
    if actor.role != "owner":
        raise DomainError("owner_required", 403, "Tindakan ini memerlukan persetujuan pemilik.")
