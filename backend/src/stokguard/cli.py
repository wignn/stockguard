import json
from pathlib import Path
from typing import Annotated, Literal
from uuid import UUID

import typer
from alembic import command
from alembic.config import Config
from sqlalchemy import select, update

from stokguard.auth.models import AuthSession, User
from stokguard.auth.passwords import hash_password
from stokguard.auth.service import add_user as create_user
from stokguard.auth.service import record_user_event, setup_business
from stokguard.core.clock import SystemClock
from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.errors import DomainError
from stokguard.core.maintenance import (
    disable_maintenance,
    enable_maintenance,
    maintenance_status,
    operation_slot,
)
from stokguard.core.transactions import write_uow
from stokguard.operations.backup import create_backup
from stokguard.operations.cleanup import apply_cleanup, preview_cleanup
from stokguard.operations.restore import restore_backup
from stokguard.operations.seed import seed_demo

cli = typer.Typer(no_args_is_help=True)


def migrate():
    root = Path(__file__).resolve().parents[2]
    command.upgrade(Config(str(root / "alembic.ini")), "head")


@cli.command()
def setup(
    name: str = typer.Option(...),
    username: str = typer.Option(...),
    password: str | None = typer.Option(None, "--password", help="Password pemilik"),
):
    if not password:
        password = typer.prompt("Password pemilik", hide_input=True, confirmation_prompt=True)
    settings = Settings()
    migrate()
    with operation_slot(settings, "cli-setup"):
        engine = make_engine(settings.database_path)
        try:
            with write_uow(engine) as db:
                business, _ = setup_business(db, name, username, password, SystemClock().now())
                business_id = business.id
            typer.echo(f"Usaha berhasil dibuat: {business_id}")
        finally:
            engine.dispose()


@cli.command("add-user")
def add_user_command(
    business_id: UUID,
    username: str,
    role: str = "staff",
    password: str | None = typer.Option(None, "--password", help="Password pengguna"),
):
    if not password:
        password = typer.prompt("Password pengguna", hide_input=True, confirmation_prompt=True)
    settings = Settings()
    with operation_slot(settings, "cli-add-user"):
        engine = make_engine(settings.database_path)
        try:
            with write_uow(engine) as db:
                create_user(db, business_id, username, password, role, SystemClock().now())
            typer.echo("Pengguna berhasil dibuat.")
        finally:
            engine.dispose()


@cli.command("change-password")
def change_password_command(
    username: str,
    password: str | None = typer.Option(None, "--password", help="Password baru"),
):
    if not password:
        password = typer.prompt("Password baru", hide_input=True, confirmation_prompt=True)
    encoded = hash_password(password)
    settings = Settings()
    with operation_slot(settings, "cli-change-password"):
        engine = make_engine(settings.database_path)
        try:
            with write_uow(engine) as db:
                user = db.scalar(select(User).where(User.username == username.strip().casefold()))
                if user is None:
                    raise typer.BadParameter("Pengguna tidak ditemukan.")
                user.password_hash = encoded
                db.execute(
                    update(AuthSession).where(AuthSession.user_id == user.id).values(revoked=True)
                )
                record_user_event(db, user, "password_changed", SystemClock().now(), source="cli")
            typer.echo("Password diubah dan sesi dicabut.")
        finally:
            engine.dispose()


@cli.command("maintenance")
def maintenance_command(
    action: Literal["on", "off", "status"],
    reason: str = typer.Option("pemeliharaan operator", "--reason"),
):
    settings = Settings()
    if action == "on":
        state = enable_maintenance(settings, reason=reason)
    elif action == "off":
        state = disable_maintenance(settings)
    else:
        state = maintenance_status(settings)
    typer.echo(json.dumps(state))


@cli.command("backup")
def backup_command(output: Annotated[Path, typer.Option("--output")]):
    settings = Settings()
    manifest = create_backup(settings, output)
    typer.echo(f"Backup berhasil dibuat: {output} (revisi {manifest.schema_revision})")


@cli.command("restore")
def restore_command(
    archive: Annotated[Path, typer.Option("--archive")],
    target: Annotated[Path, typer.Option("--target")],
):
    report = restore_backup(archive, target)
    typer.echo(
        f"Restore berhasil ke {target}: {report.evidence_files} berkas bukti, "
        f"{report.revoked_sessions} sesi dicabut, "
        f"{report.requeued_jobs} pekerjaan OCR diantrekan ulang."
    )


@cli.command("cleanup")
def cleanup_command(
    preview: bool = typer.Option(False, "--preview"),
    apply: bool = typer.Option(False, "--apply"),
    token: str = typer.Option("", "--token"),
):
    settings = Settings()
    if preview == apply:
        raise typer.BadParameter("Pilih tepat salah satu: --preview atau --apply.")
    if preview:
        result = preview_cleanup(settings)
        typer.echo(json.dumps(result.model_dump()))
    else:
        report = apply_cleanup(settings, token)
        typer.echo(json.dumps(report.model_dump()))


@cli.command("seed-demo")
def seed_demo_command(
    owner_username: str = typer.Option("demo-pemilik", "--owner-username"),
    staff_username: str = typer.Option("demo-staf", "--staff-username"),
    owner_password: str | None = typer.Option(None, "--owner-password"),
    staff_password: str | None = typer.Option(None, "--staff-password"),
):
    if not owner_password:
        owner_password = typer.prompt(
            "Password pemilik demo", hide_input=True, confirmation_prompt=True
        )
    if not staff_password:
        staff_password = typer.prompt(
            "Password staf demo", hide_input=True, confirmation_prompt=True
        )
    settings = Settings()
    migrate()
    try:
        business_id = seed_demo(
            settings,
            owner_username=owner_username,
            owner_password=owner_password,
            staff_username=staff_username,
            staff_password=staff_password,
        )
    except DomainError as error:
        typer.echo(f"Seed dibatalkan: {error.message} Data lama tidak diubah.", err=True)
        if error.code == "username_exists":
            typer.echo(
                "Gunakan akun yang sudah ada, atau buat demo baru dengan kedua nama berbeda: "
                "make seed DEMO_OWNER=pemilik-demo-2 DEMO_STAFF=staf-demo-2. "
                "Alternatif: pilih STOKGUARD_DATA_DIR terpisah.",
                err=True,
            )
        raise typer.Exit(1) from None
    typer.echo(f"Data demonstrasi berhasil dibuat: {business_id}")


@cli.command("ocr-check")
def ocr_check():
    from stokguard.ocr.engine import TesseractEngine

    settings = Settings()
    adapter = TesseractEngine(settings.tesseract_command, settings.ocr_languages)
    if not adapter.available():
        typer.echo("OCR unavailable: executable Tesseract belum tersedia.")
        raise typer.Exit(1)
    typer.echo("Executable Tesseract tersedia; gunakan tes integrasi untuk memeriksa OCR.")


@cli.command("worker")
def worker_command():
    from stokguard.ocr.engine import TesseractEngine
    from stokguard.ocr.worker import run_worker

    settings = Settings()
    try:
        run_worker(settings, TesseractEngine(settings.tesseract_command, settings.ocr_languages))
    except KeyboardInterrupt:
        typer.echo("Worker dihentikan.")


if __name__ == "__main__":
    cli()
