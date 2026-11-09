from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.engine import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from stokguard.core.errors import DomainError


@contextmanager
def write_uow(engine: Engine) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        try:
            session.connection().exec_driver_sql("BEGIN IMMEDIATE")
            yield session
            session.commit()
        except OperationalError as exc:
            session.rollback()
            if "locked" in str(exc.orig).lower() or "busy" in str(exc.orig).lower():
                raise DomainError(
                    "database_busy", 503, "Penyimpanan sedang sibuk. Silakan coba lagi."
                ) from exc
            raise
        except BaseException:
            session.rollback()
            raise
