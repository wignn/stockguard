from datetime import timedelta

from sqlalchemy import select


def login(client, **changes):
    payload = {"username": "owner-a", "password": "test-password-owner", "mode": "web"}
    return client.post("/api/v1/auth/login", json=payload | changes)


def test_login_cookie_security_and_csrf(client):
    response = login(client)
    assert response.status_code == 200
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie and "SameSite=lax" in cookie and "Path=/api/v1" in cookie
    assert "token" not in response.json()
    assert client.get("/api/v1/auth/session").status_code == 200
    assert client.post("/api/v1/auth/logout").status_code == 403
    client.headers["X-CSRF-Token"] = response.json()["csrf_token"]
    assert client.post("/api/v1/auth/logout").status_code == 200
    assert client.get("/api/v1/auth/session").status_code == 401


def test_cookie_and_bearer_rejected(authenticated):
    assert (
        authenticated.get(
            "/api/v1/auth/session", headers={"Authorization": "Bearer ambiguous"}
        ).status_code
        == 401
    )


def test_expiry_at_seven_days(client, app):
    assert login(client).status_code == 200
    app.state.clock.value += timedelta(days=7)
    assert client.get("/api/v1/auth/session").status_code == 401


def test_logout_and_password_change_revoke_sessions(authenticated, app):
    from stokguard.auth.models import AuthSession
    from stokguard.core.transactions import write_uow

    token_response = authenticated.post(
        "/api/v1/auth/login",
        json={"username": "owner-a", "password": "test-password-owner", "mode": "token"},
    )
    assert token_response.status_code == 200
    token = token_response.json()["token"]
    with write_uow(app.state.engine) as db:
        sessions = db.scalars(select(AuthSession)).all()
        assert all(item.token_hash != token for item in sessions)
    response = authenticated.post(
        "/api/v1/auth/change-password",
        json={"current_password": "test-password-owner", "new_password": "new-password-owner"},
    )
    assert response.status_code == 200
    from stokguard.audit.models import AuditEvent

    with write_uow(app.state.engine) as db:
        assert db.scalar(select(AuditEvent).where(AuditEvent.action == "password_changed"))
    authenticated.cookies.clear()
    assert (
        authenticated.get(
            "/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"}
        ).status_code
        == 401
    )
    assert login(authenticated).status_code == 401
    assert login(authenticated, password="new-password-owner").status_code == 200


def test_login_rate_limit_and_unknown_account(client):
    for _ in range(5):
        assert login(client, username="unknown", password="wrong").status_code == 401
    response = login(client, username="unknown", password="wrong")
    assert response.status_code == 429
    assert response.headers["retry-after"]


def test_origin_must_be_allowed(client):
    assert login(client).status_code == 200
    client.headers["Origin"] = "https://untrusted.example"
    assert login(client).status_code == 403


def test_secure_cookie_config(client, app):
    app.state.settings.secure_cookies = True
    # HTTPS is required when secure cookies are enabled.
    assert login(client).status_code == 403


def test_token_rejected_over_remote_plain_http(client, app):
    from fastapi.testclient import TestClient

    response = login(client, mode="token")
    token = response.json()["token"]
    with TestClient(app, base_url="http://inventory.example") as remote:
        result = remote.get("/api/v1/auth/session", headers={"Authorization": f"Bearer {token}"})
    assert result.status_code == 403
    assert result.json()["error"]["code"] == "https_required"


def test_https_cookie_and_auth_audit(app):
    from fastapi.testclient import TestClient
    from sqlalchemy.orm import Session

    from stokguard.audit.models import AuditEvent

    app.state.settings.secure_cookies = True
    with TestClient(
        app, base_url="https://inventory.example", headers={"Origin": "http://localhost:3000"}
    ) as secure:
        response = login(secure)
        assert response.status_code == 200
        assert "Secure" in response.headers["set-cookie"]
        secure.headers["X-CSRF-Token"] = response.json()["csrf_token"]
        assert secure.post("/api/v1/auth/logout").status_code == 200
    with Session(app.state.engine) as db:
        actions = set(db.scalars(select(AuditEvent.action)))
        assert {"session_created", "session_revoked"} <= actions
        for event in db.scalars(select(AuditEvent)):
            assert "password" not in str(event.changes)
            assert "token" not in str(event.changes)


def test_setup_has_no_default_password(app):
    from stokguard.auth.models import User
    from stokguard.core.transactions import write_uow

    with write_uow(app.state.engine) as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 2
        assert all(user.password_hash.startswith("$argon2id$") for user in users)
        assert all("test-password" not in user.password_hash for user in users)
