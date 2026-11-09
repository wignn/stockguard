from __future__ import annotations

import json
import os
import sys
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from stokguard.core.config import Settings
from stokguard.core.errors import DomainError

_PROCESS_LOCK = threading.RLock()
_ACTIVE_SLOTS: dict[Path, set[str]] = {}


def _maint_dir(settings: Settings) -> Path:
    path = settings.data_dir / ".maintenance"
    (path / "inflight").mkdir(parents=True, exist_ok=True)
    return path


def _try_lock_fd(fd: int) -> bool:
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except OSError:
        return False


def _unlock_fd(fd: int) -> None:
    try:
        if sys.platform == "win32":
            import msvcrt

            os.lseek(fd, 0, os.SEEK_SET)
            msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_UN)
    except OSError:
        pass


@contextmanager
def _coordinator_lock(settings: Settings, timeout: float = 10.0) -> Iterator[Path]:
    maint = _maint_dir(settings)
    lock_file = maint / "coordinator.lock"
    deadline = time.monotonic() + timeout
    with _PROCESS_LOCK:
        fd = os.open(str(lock_file), os.O_CREAT | os.O_RDWR)
        try:
            while not _try_lock_fd(fd):
                if time.monotonic() >= deadline:
                    raise TimeoutError("Gagal memperoleh kunci koordinasi pemeliharaan.")
                time.sleep(0.01)
            try:
                yield maint
            finally:
                _unlock_fd(fd)
        finally:
            os.close(fd)


def _count_live_slots(maint: Path) -> int:
    inflight_dir = maint / "inflight"
    data_root = maint.parent.resolve()
    in_proc = len(_ACTIVE_SLOTS.get(data_root, set()))
    external_live = 0
    for slot_file in list(inflight_dir.glob("*.lock")):
        slot_id = slot_file.stem
        if slot_id in _ACTIVE_SLOTS.get(data_root, set()):
            continue
        try:
            fd = os.open(str(slot_file), os.O_RDWR)
        except OSError:
            continue
        try:
            if _try_lock_fd(fd):
                # Dead process left a lock file behind; clean it up
                _unlock_fd(fd)
                os.close(fd)
                slot_file.unlink(missing_ok=True)
            else:
                external_live += 1
                os.close(fd)
        except OSError:
            try:
                os.close(fd)
            except OSError:
                pass
    return in_proc + external_live


def maintenance_status(settings: Settings) -> dict[str, Any]:
    with _coordinator_lock(settings) as maint:
        state_file = maint / "state.json"
        paused_file = maint / "worker_paused.json"
        inflight = _count_live_slots(maint)
        if not state_file.exists():
            return {
                "active": False,
                "reason": None,
                "enabled_at": None,
                "worker_paused": False,
                "inflight_count": inflight,
            }
        data = json.loads(state_file.read_text(encoding="utf-8"))
        return {
            "active": bool(data.get("active", True)),
            "reason": data.get("reason"),
            "enabled_at": data.get("enabled_at"),
            "worker_paused": paused_file.exists(),
            "inflight_count": inflight,
        }


def enable_maintenance(settings: Settings, reason: str = "maintenance") -> dict[str, Any]:
    with _coordinator_lock(settings) as maint:
        state_file = maint / "state.json"
        payload = {
            "active": True,
            "reason": reason,
            "enabled_at": datetime.now(UTC).isoformat(),
        }
        state_file.write_text(json.dumps(payload), encoding="utf-8")
    return maintenance_status(settings)


def disable_maintenance(settings: Settings) -> dict[str, Any]:
    with _coordinator_lock(settings) as maint:
        (maint / "state.json").unlink(missing_ok=True)
        (maint / "worker_paused.json").unlink(missing_ok=True)
    return maintenance_status(settings)


def acknowledge_worker_pause(settings: Settings) -> None:
    with _coordinator_lock(settings) as maint:
        if (maint / "state.json").exists():
            (maint / "worker_paused.json").write_text(
                json.dumps({"paused_at": datetime.now(UTC).isoformat()}),
                encoding="utf-8",
            )


def ensure_not_in_maintenance(settings: Settings) -> None:
    status = maintenance_status(settings)
    if status["active"]:
        raise DomainError(
            "maintenance_mode",
            503,
            "Sistem sedang dalam mode pemeliharaan. Coba lagi setelah pemeliharaan selesai.",
        )


@contextmanager
def operation_slot(settings: Settings, kind: str = "mutation") -> Iterator[None]:
    slot_id = f"{kind}-{uuid4().hex}"
    data_root = settings.data_dir.resolve()
    with _coordinator_lock(settings) as maint:
        if (maint / "state.json").exists():
            raise DomainError(
                "maintenance_mode",
                503,
                "Sistem sedang dalam mode pemeliharaan. Coba lagi setelah pemeliharaan selesai.",
            )
        slot_path = maint / "inflight" / f"{slot_id}.lock"
        fd = os.open(str(slot_path), os.O_CREAT | os.O_RDWR)
        os.write(fd, slot_id.encode("utf-8"))
        _try_lock_fd(fd)
        _ACTIVE_SLOTS.setdefault(data_root, set()).add(slot_id)
    try:
        yield
    finally:
        with _coordinator_lock(settings):
            _ACTIVE_SLOTS.get(data_root, set()).discard(slot_id)
            _unlock_fd(fd)
            os.close(fd)
            slot_path.unlink(missing_ok=True)


def wait_for_drain(settings: Settings, timeout_seconds: float = 30.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    while True:
        status = maintenance_status(settings)
        if status["inflight_count"] == 0:
            return
        if time.monotonic() >= deadline:
            raise TimeoutError(
                "Operasi yang sedang berjalan belum selesai dalam batas waktu drain."
            )
        time.sleep(0.02)


@contextmanager
def maintenance_drain_scope(
    settings: Settings, reason: str, timeout_seconds: float = 30.0
) -> Iterator[None]:
    was_active = maintenance_status(settings)["active"]
    if not was_active:
        enable_maintenance(settings, reason=reason)
    try:
        wait_for_drain(settings, timeout_seconds=timeout_seconds)
        yield
    finally:
        if not was_active:
            disable_maintenance(settings)
