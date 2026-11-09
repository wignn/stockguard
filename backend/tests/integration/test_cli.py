def test_cli_setup_prompts_password_and_migrates(tmp_path, monkeypatch):
    from typer.testing import CliRunner

    from stokguard.cli import cli

    monkeypatch.setenv("STOKGUARD_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["setup", "--name", "CLI Test", "--username", "cli-owner"],
        input="cli-test-password\ncli-test-password\n",
    )
    assert result.exit_code == 0, result.output
    assert "cli-test-password" not in result.output
    assert (tmp_path / "stokguard.db").exists()
    assert "Usaha berhasil dibuat" in result.output

    from sqlalchemy import inspect, select
    from sqlalchemy.orm import Session

    from stokguard.audit.models import AuditEvent
    from stokguard.auth.models import User
    from stokguard.core.db import make_engine

    engine = make_engine(tmp_path / "stokguard.db")
    assert {
        "products",
        "stock_balances",
        "stock_movements",
        "idempotency_records",
        "stocktakes",
        "investigation_cases",
        "case_submissions",
        "approval_decisions",
        "reversal_requests",
        "evidence_files",
        "evidence_links",
        "ocr_jobs",
        "transaction_drafts",
        "draft_lines",
    } <= set(inspect(engine).get_table_names())
    with Session(engine) as db:
        owner = db.scalar(select(User))
        owner_id = owner.id
        business_id = db.scalar(select(AuditEvent)).business_id
    added = runner.invoke(
        cli,
        ["add-user", business_id, "cli-staff"],
        input="staff-test-password\nstaff-test-password\n",
    )
    assert added.exit_code == 0, added.output
    changed = runner.invoke(
        cli,
        ["change-password", "cli-owner"],
        input="changed-test-password\nchanged-test-password\n",
    )
    assert changed.exit_code == 0, changed.output
    assert "changed-test-password" not in changed.output
    with Session(engine) as db:
        events = db.scalars(
            select(AuditEvent).where(
                AuditEvent.action == "password_changed", AuditEvent.user_id == owner_id
            )
        ).all()
        assert len(events) == 1
        assert events[0].changes == {"source": "cli"}
    engine.dispose()


def test_cli_seed_duplicate_reports_recovery_without_changing_existing_data(tmp_path, monkeypatch):
    from sqlalchemy import func, select
    from sqlalchemy.orm import Session
    from typer.testing import CliRunner

    from stokguard.auth.models import User
    from stokguard.businesses.models import Business
    from stokguard.cli import cli
    from stokguard.core.db import make_engine
    from stokguard.core.errors import DomainError
    from stokguard.inventory.models import StockMovement

    monkeypatch.setenv("STOKGUARD_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    passwords = (
        "demo-owner-password\ndemo-owner-password\n"
        "demo-staff-password\ndemo-staff-password\n"
    )
    first = runner.invoke(cli, ["seed-demo"], input=passwords)
    assert first.exit_code == 0, first.output
    engine = make_engine(tmp_path / "stokguard.db")

    def snapshot():
        with Session(engine) as db:
            return (
                db.scalar(select(func.count()).select_from(Business)),
                db.scalar(select(func.count()).select_from(StockMovement)),
                list(db.execute(select(User.username, User.password_hash).order_by(User.username))),
            )

    try:
        before = snapshot()
        for arguments in ([], ["--owner-username", "different-owner"]):
            result = runner.invoke(cli, ["seed-demo", *arguments], input=passwords)
            assert result.exit_code == 1
            assert not isinstance(result.exception, DomainError)
            assert "Username sudah digunakan" in result.output
            assert "DEMO_OWNER" in result.output
            assert "DEMO_STAFF" in result.output
            assert "Data lama tidak diubah" in result.output
            assert "Traceback" not in result.output
            assert "demo-owner-password" not in result.output
            assert "demo-staff-password" not in result.output
            assert snapshot() == before
    finally:
        engine.dispose()
