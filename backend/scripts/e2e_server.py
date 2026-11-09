"""Isolated loopback API for browser tests; never provisions the working database."""
import os
from tempfile import TemporaryDirectory

import uvicorn

from stokguard.auth.service import add_user, setup_business
from stokguard.cli import migrate
from stokguard.core.clock import SystemClock
from stokguard.core.config import Settings
from stokguard.core.db import make_engine
from stokguard.core.transactions import write_uow
from stokguard.main import create_app


def main():
    with TemporaryDirectory(prefix="stokguard-e2e-") as directory:
        os.environ["STOKGUARD_DATA_DIR"] = directory
        migrate()
        settings = Settings()
        engine = make_engine(settings.database_path)
        password = os.environ["STOKGUARD_E2E_PASSWORD"]
        with write_uow(engine) as db:
            now = SystemClock().now()
            business, _ = setup_business(db, "Toko uji browser", "e2e-owner", password, now)
            add_user(db, business.id, "e2e-staff", password, "staff", now)
            setup_business(db, "Usaha Kosong E2E", "e2e-empty-owner", password, now)
        engine.dispose()
        uvicorn.run(create_app(settings), host="127.0.0.1", port=8001, log_level="warning")


if __name__ == "__main__":
    main()
