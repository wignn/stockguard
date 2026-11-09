from fastapi import APIRouter, Request, Response
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from stokguard.auth.dependencies import COOKIE, check_origin, require_session
from stokguard.auth.models import AuthSession, User
from stokguard.auth.passwords import DUMMY_HASH, hash_password, verify_password
from stokguard.auth.schemas import LoginInput, PasswordChange
from stokguard.auth.service import record_user_event
from stokguard.auth.sessions import issue_session, membership_views, session_view
from stokguard.core.errors import DomainError
from stokguard.core.transactions import write_uow

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post("/login")
def login(payload: LoginInput, request: Request, response: Response):
    settings = request.app.state.settings
    if payload.mode == "web":
        check_origin(request)
    secure = request.url.scheme == "https"
    if (settings.secure_cookies or payload.mode == "token") and not secure:
        loopback = request.url.hostname in {"localhost", "127.0.0.1", "testserver"}
        if settings.secure_cookies or not loopback:
            raise DomainError("https_required", 403, "Koneksi HTTPS diperlukan.")
    username = payload.username.strip().casefold()
    ip = request.client.host if request.client else "unknown"
    now = request.app.state.clock.now()
    limiter = request.app.state.login_limiter
    limiter.check(username, ip, now)
    with Session(request.app.state.engine) as db:
        user = db.scalar(select(User).where(User.username == username))
        encoded = user.password_hash if user else DUMMY_HASH
        valid = verify_password(payload.password, encoded)
        user_id = user.id if user else None
        active = user.active if user else False
    if not valid or not active:
        limiter.failed(username, ip, now)
        raise DomainError("login_failed", 401, "Username atau password salah. Silakan coba lagi.")
    with write_uow(request.app.state.engine) as db:
        user = db.get(User, user_id)
        # The password may have changed while its expensive hash was being checked.
        if user is None or not user.active or user.password_hash != encoded:
            raise DomainError(
                "login_failed", 401, "Username atau password salah. Silakan coba lagi."
            )
        session, token = issue_session(db, user, now)
        result = session_view(db, session, user)
        record_user_event(
            db,
            user,
            "session_created",
            now,
            source=payload.mode,
            request_id=request.state.request_id,
        )
    response.headers["Cache-Control"] = "no-store"
    if payload.mode == "web":
        response.set_cookie(
            COOKIE,
            token,
            httponly=True,
            secure=settings.secure_cookies or secure,
            samesite="lax",
            path="/api/v1",
            max_age=7 * 86400,
        )
    else:
        result.pop("csrf_token", None)
        result["token"] = token
    return result


@router.get("/session")
def current_session(request: Request, response: Response):
    with Session(request.app.state.engine) as db:
        session, user = require_session(request, db)
        response.headers["Cache-Control"] = "no-store"
        return session_view(db, session, user)


@router.get("/memberships")
def memberships(request: Request):
    with Session(request.app.state.engine) as db:
        _, user = require_session(request, db)
        return membership_views(db, user)


@router.post("/logout")
def logout(request: Request, response: Response):
    with write_uow(request.app.state.engine) as db:
        session, user = require_session(request, db)
        session.revoked = True
        record_user_event(
            db,
            user,
            "session_revoked",
            request.app.state.clock.now(),
            source="api",
            request_id=request.state.request_id,
        )
    response.delete_cookie(COOKIE, path="/api/v1")
    return {"status": "ok"}


@router.post("/change-password")
def change_password(payload: PasswordChange, request: Request, response: Response):
    with Session(request.app.state.engine) as db:
        _, user = require_session(request, db)
        user_id, old_hash = user.id, user.password_hash
    if not verify_password(payload.current_password, old_hash):
        raise DomainError("password_invalid", 422, "Password saat ini tidak sesuai.")
    new_hash = hash_password(payload.new_password)
    with write_uow(request.app.state.engine) as db:
        _, user = require_session(request, db)
        if user.id != user_id or user.password_hash != old_hash:
            raise DomainError("session_changed", 409, "Akun telah berubah. Silakan masuk kembali.")
        user.password_hash = new_hash
        db.execute(update(AuthSession).where(AuthSession.user_id == user_id).values(revoked=True))
        record_user_event(
            db,
            user,
            "password_changed",
            request.app.state.clock.now(),
            source="api",
            request_id=request.state.request_id,
        )
    response.delete_cookie(COOKIE, path="/api/v1")
    return {"status": "ok"}
