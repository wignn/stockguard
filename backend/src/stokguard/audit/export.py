import csv
import json
from collections.abc import Iterator
from datetime import UTC, date, datetime, time
from io import StringIO
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import and_, or_, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from stokguard.audit.models import AuditEvent
from stokguard.businesses.models import Business
from stokguard.core.errors import DomainError
from stokguard.core.numbers import format_quantity, parse_quantity

FORMULA_PREFIXES = ("=", "+", "-", "@", "\t", "\r")
CSV_COLUMNS = [
    "id",
    "occurred_at",
    "user_id",
    "action",
    "entity_type",
    "entity_id",
    "quantity",
    "note",
    "changes",
]


def sanitize_csv_text(value: str) -> str:
    if value and value.startswith(FORMULA_PREFIXES):
        return f"'{value}"
    return value


def format_signed_quantity(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("Kuantitas tidak valid.")
    if value == "0":
        return "0"
    if value.startswith("-"):
        milli = -parse_quantity(value[1:], 1)
    else:
        milli = parse_quantity(value, 1)
    return format_quantity(milli)


def _parse_bound(raw: str, tz_name: str) -> str:
    zone = ZoneInfo(tz_name)
    try:
        if len(raw) == 10 and raw[4] == "-" and raw[7] == "-":
            parsed_date = date.fromisoformat(raw)
            dt = datetime.combine(parsed_date, time.min, tzinfo=zone)
        else:
            dt = datetime.fromisoformat(raw)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=zone)
    except ValueError as exc:
        raise DomainError("invalid_date", 422, "Format tanggal tidak valid.") from exc
    return dt.astimezone(UTC).isoformat()


def parse_time_bounds(
    db: Session, business_id: UUID | str, start: str | None, end: str | None
) -> tuple[str | None, str | None]:
    if not start and not end:
        return None, None
    business = db.get(Business, str(business_id))
    tz_name = business.timezone if business else "Asia/Jakarta"
    start_utc = _parse_bound(start, tz_name) if start else None
    end_utc = _parse_bound(end, tz_name) if end else None
    return start_utc, end_utc


def audit_filters(business_id: UUID | str, start_utc: str | None, end_utc: str | None) -> list:
    filters = [AuditEvent.business_id == str(business_id)]
    if start_utc:
        filters.append(AuditEvent.occurred_at >= start_utc)
    if end_utc:
        filters.append(AuditEvent.occurred_at < end_utc)
    return filters


def _extract_quantity(changes: dict) -> str:
    raw = changes.get("quantity")
    if raw is None:
        raw = changes.get("difference_quantity")
    if raw is None:
        return ""
    return format_signed_quantity(str(raw))


def _extract_note(changes: dict) -> str:
    for key in ("note", "reason", "name"):
        val = changes.get(key)
        if isinstance(val, str) and val:
            return sanitize_csv_text(val)
    return ""


def _sanitize_changes(changes: dict) -> str:
    safe = {
        k: (
            format_signed_quantity(v)
            if k in {"quantity", "difference_quantity"} and isinstance(v, str)
            else sanitize_csv_text(v)
            if isinstance(v, str)
            else v
        )
        for k, v in (changes or {}).items()
    }
    return sanitize_csv_text(json.dumps(safe, ensure_ascii=False, sort_keys=True))


def stream_audit_csv(
    engine: Engine,
    business_id: UUID | str,
    start_utc: str | None,
    end_utc: str | None,
    *,
    batch_size: int = 100,
) -> Iterator[str]:
    buf = StringIO()
    writer = csv.writer(buf, lineterminator="\r\n")
    writer.writerow(CSV_COLUMNS)
    yield buf.getvalue()
    buf.seek(0)
    buf.truncate(0)

    cursor: tuple[str, str] | None = None
    while True:
        with Session(engine) as db:
            filters = audit_filters(business_id, start_utc, end_utc)
            if cursor is not None:
                last_time, last_id = cursor
                filters.append(
                    or_(
                        AuditEvent.occurred_at > last_time,
                        and_(AuditEvent.occurred_at == last_time, AuditEvent.id > last_id),
                    )
                )
            rows = db.scalars(
                select(AuditEvent)
                .where(*filters)
                .order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
                .limit(batch_size)
            ).all()
            if not rows:
                break
            for row in rows:
                changes = row.changes if isinstance(row.changes, dict) else {}
                writer.writerow(
                    [
                        sanitize_csv_text(row.id),
                        sanitize_csv_text(row.occurred_at),
                        sanitize_csv_text(row.user_id),
                        sanitize_csv_text(row.action),
                        sanitize_csv_text(row.entity_type),
                        sanitize_csv_text(row.entity_id),
                        _extract_quantity(changes),
                        _extract_note(changes),
                        _sanitize_changes(changes),
                    ]
                )
            cursor = (rows[-1].occurred_at, rows[-1].id)
        yield buf.getvalue()
        buf.seek(0)
        buf.truncate(0)
