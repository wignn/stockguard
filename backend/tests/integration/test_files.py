from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from test_approvals import cases_url, decision, prepare_case, submit


def image_bytes(fmt="PNG", size=(12, 12)):
    stream = BytesIO()
    Image.new("RGB", size, "white").save(stream, format=fmt)
    return stream.getvalue()


def files_url(app, business_id=None):
    return f"/api/v1/businesses/{business_id or app.state.test_business_id}/files"


def upload(client, app, data=None, name="nota.png"):
    return client.post(
        files_url(app), files={"file": (name, image_bytes() if data is None else data, "text/html")}
    )


@pytest.mark.parametrize("fmt,mime", [("JPEG", "image/jpeg"), ("PNG", "image/png")])
def test_real_jpeg_png_accepted(authenticated, app, fmt, mime):
    data = image_bytes(fmt)
    response = upload(authenticated, app, data)
    assert response.status_code == 201, response.text
    item = response.json()
    assert item["mime_type"] == mime and item["width"] == 12
    assert item["size_bytes"] == len(data) and len(item["sha256"]) == 64
    content = authenticated.get(files_url(app) + f"/{item['id']}/content")
    assert content.status_code == 200 and content.content == data
    assert content.headers["content-type"] == mime
    assert content.headers["x-content-type-options"] == "nosniff"
    assert content.headers["cache-control"] == "private, no-store"
    assert content.headers["content-disposition"].startswith("attachment;")


def test_signature_not_extension(authenticated, app):
    assert upload(authenticated, app, b"<script>alert(1)</script>").status_code == 422
    assert upload(authenticated, app, image_bytes("GIF")).status_code == 422
    assert upload(authenticated, app, image_bytes()[:40]).status_code == 422
    assert upload(authenticated, app, name="nota.html").status_code == 201


def test_5_mib_and_20_megapixel_limits(authenticated, app):
    data = image_bytes()
    padded = data + b"\0" * (5 * 1024 * 1024 - len(data))
    assert upload(authenticated, app, padded).status_code == 201
    assert upload(authenticated, app, padded + b"x").status_code == 413
    assert upload(authenticated, app, image_bytes(size=(5000, 4000))).status_code == 201
    assert upload(authenticated, app, image_bytes(size=(5001, 4000))).status_code == 422


def test_path_name_cannot_escape_root(authenticated, app):
    response = upload(authenticated, app, name="../../outside.png")
    assert response.status_code == 201
    item = response.json()
    assert item["original_name"] == "outside.png"
    assert "storage_key" not in item
    root = app.state.settings.data_dir
    assert not (root.parent / "outside.png").exists()
    assert authenticated.get(files_url(app) + f"/{item['id']}/content").status_code == 200


def test_cross_tenant_link_download_hidden(authenticated, staff, app):
    _, _, case = prepare_case(authenticated, staff, app)
    item = upload(authenticated, app).json()
    foreign = files_url(app, app.state.other_business_id)
    for suffix in [f"/{item['id']}", f"/{item['id']}/content"]:
        assert authenticated.get(foreign + suffix).status_code == 404
    assert (
        authenticated.post(
            f"/api/v1/businesses/{app.state.other_business_id}/cases/{case['id']}/evidence",
            json={"file_id": item["id"]},
        ).status_code
        == 404
    )
    assert (
        authenticated.post(
            cases_url(app) + f"/{case['id']}/evidence", json={"file_id": str(uuid4())}
        ).status_code
        == 404
    )
    from fastapi.testclient import TestClient

    with TestClient(app) as other:
        other.headers["Origin"] = "http://localhost:3000"
        login = other.post(
            "/api/v1/auth/login",
            json={
                "username": "owner-b",
                "password": "test-password-other",
                "mode": "web",
            },
        )
        other.headers["X-CSRF-Token"] = login.json()["csrf_token"]
        foreign_file = other.post(
            foreign, files={"file": ("nota.png", image_bytes(), "image/png")}
        ).json()
        assert other.get(files_url(app) + f"/{item['id']}/content").status_code == 404
    assert (
        staff.post(
            cases_url(app) + f"/{case['id']}/evidence", json={"file_id": foreign_file["id"]}
        ).status_code
        == 404
    )


def test_duplicate_hash_warns_not_autobooks(authenticated, app):
    from stokguard.inventory.models import StockMovement

    first = upload(authenticated, app).json()
    second = upload(authenticated, app).json()
    assert first["duplicate_ids"] == []
    assert second["duplicate_ids"] == [first["id"]]
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 0


def test_interrupted_upload_leaves_no_visible_record(authenticated, app):
    from stokguard.auth.dependencies import Actor
    from stokguard.files.models import EvidenceFile
    from stokguard.files.service import store_upload

    session = authenticated.get("/api/v1/auth/session").json()
    with Session(app.state.engine) as db:
        from stokguard.auth.models import AuthSession

        auth_session = db.scalar(
            select(AuthSession).where(AuthSession.user_id == app.state.owner_id)
        )
        actor = Actor(
            user_id=app.state.owner_id,
            business_id=app.state.test_business_id,
            session_id=auth_session.id,
            role="owner",
        )
    assert session

    class Interrupted:
        def read(self, _size):
            raise OSError("upload interrupted")

    with pytest.raises(OSError, match="interrupted"):
        store_upload(
            app.state.engine,
            actor,
            Interrupted(),
            "nota.png",
            root=app.state.settings.data_dir / "evidence",
            now=app.state.clock.now(),
        )
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(EvidenceFile)) == 0
    assert not list((app.state.settings.data_dir / "evidence").rglob("*.part"))


def test_case_evidence_is_explicit_and_submission_snapshot_immutable(authenticated, staff, app):
    from stokguard.inventory.models import StockMovement

    _, count, case = prepare_case(authenticated, staff, app)
    item = upload(staff, app).json()
    linked = staff.post(cases_url(app) + f"/{case['id']}/evidence", json={"file_id": item["id"]})
    assert linked.status_code == 201, linked.text
    submitted = submit(
        staff, app, case, count, missing_evidence_reason="", evidence_ids=[item["id"]]
    )
    assert submitted.status_code == 201, submitted.text
    assert submitted.json()["snapshot"]["evidence_ids"] == [item["id"]]
    assert submitted.json()["snapshot"]["missing_evidence"] is False
    from stokguard.auth.dependencies import Actor
    from stokguard.core.errors import DomainError
    from stokguard.core.transactions import write_uow
    from stokguard.files.schemas import EvidenceTarget
    from stokguard.files.service import link_evidence

    with pytest.raises(DomainError, match="Tambahkan bukti"):
        with write_uow(app.state.engine) as db:
            db.info["now"] = app.state.clock.now()
            actor = Actor(
                user_id=app.state.owner_id,
                business_id=app.state.test_business_id,
                session_id=uuid4(),
                role="owner",
            )
            link_evidence(
                db, actor, item["id"], EvidenceTarget(kind="submission", id=submitted.json()["id"])
            )
    approved = decision(authenticated, app, case, submitted.json())
    assert approved.status_code == 200
    before = approved.json()["snapshot"]
    late = upload(staff, app, image_bytes(size=(13, 13))).json()
    assert (
        staff.post(
            cases_url(app) + f"/{case['id']}/evidence", json={"file_id": late["id"]}
        ).status_code
        == 201
    )
    detail = authenticated.get(files_url(app) + f"/{late['id']}").json()
    assert detail["links"][0]["target_type"] == "case"
    from stokguard.approvals.models import ApprovalDecision

    with Session(app.state.engine) as db:
        assert db.get(ApprovalDecision, approved.json()["id"]).snapshot == before
        assert db.scalar(select(func.count()).select_from(StockMovement)) == 2


def test_upload_audit_failure_removes_bytes_and_record(authenticated, app, monkeypatch):
    from stokguard.files import service
    from stokguard.files.models import EvidenceFile

    def fail(*args, **kwargs):
        raise RuntimeError("audit unavailable")

    monkeypatch.setattr(service, "append_event", fail)
    with pytest.raises(RuntimeError, match="audit unavailable"):
        upload(authenticated, app)
    with Session(app.state.engine) as db:
        assert db.scalar(select(func.count()).select_from(EvidenceFile)) == 0
    assert not list((app.state.settings.data_dir / "evidence").iterdir())


def test_movement_evidence_does_not_modify_ledger(authenticated, staff, app):
    product, _, _ = prepare_case(authenticated, staff, app)
    base = f"/api/v1/businesses/{app.state.test_business_id}"
    movement = authenticated.get(base + "/movements").json()["items"][0]
    item = upload(authenticated, app).json()
    response = authenticated.post(
        base + f"/movements/{movement['id']}/evidence", json={"file_id": item["id"]}
    )
    assert response.status_code == 201, response.text
    assert authenticated.get(base + f"/movements/{movement['id']}").json() == movement
    assert authenticated.get(base + f"/products/{product['id']}").json()["balance_version"] == 1
