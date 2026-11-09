import importlib

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text


def test_health_and_openapi(tmp_path):
    config = importlib.import_module("stokguard.core.config")
    main = importlib.import_module("stokguard.main")
    app = main.create_app(config.Settings(data_dir=tmp_path))
    with TestClient(app) as client:
        response = client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok"}
        assert response.headers["x-request-id"]
        assert client.get("/openapi.json").json()["info"]["title"] == "StokGuard API"


def test_db_pragmas_on_each_connection(tmp_path):
    db = importlib.import_module("stokguard.core.db")
    engine = db.make_engine(tmp_path / "test.db")
    try:
        with engine.connect() as first, engine.connect() as second:
            for conn in [first, second]:
                assert conn.exec_driver_sql("PRAGMA foreign_keys").scalar() == 1
                assert conn.exec_driver_sql("PRAGMA journal_mode").scalar() == "wal"
                assert conn.exec_driver_sql("PRAGMA busy_timeout").scalar() == 5000
    finally:
        engine.dispose()


def test_uow_rolls_back(tmp_path):
    db = importlib.import_module("stokguard.core.db")
    transactions = importlib.import_module("stokguard.core.transactions")
    engine = db.make_engine(tmp_path / "test.db")
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE TABLE sample (id INTEGER PRIMARY KEY)"))
        with pytest.raises(RuntimeError, match="interrupted"):
            with transactions.write_uow(engine) as session:
                session.execute(text("INSERT INTO sample VALUES (1)"))
                raise RuntimeError("interrupted")
        with engine.connect() as conn:
            assert conn.execute(text("SELECT COUNT(*) FROM sample")).scalar() == 0
        with transactions.write_uow(engine) as session:
            session.execute(text("INSERT INTO sample VALUES (2)"))
        with engine.connect() as conn:
            assert conn.execute(text("SELECT id FROM sample")).scalar() == 2
    finally:
        engine.dispose()


def test_network_data_path_rejected():
    config = importlib.import_module("stokguard.core.config")
    with pytest.raises(ValueError):
        config.Settings(data_dir=r"\\server\share\stock")
