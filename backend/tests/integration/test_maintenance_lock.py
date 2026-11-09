import multiprocessing
import sys

import pytest

from stokguard.core.config import Settings
from stokguard.core.maintenance import _coordinator_lock


def _hold_coordinator(data_dir, ready, release):
    with _coordinator_lock(Settings(data_dir=data_dir)):
        ready.set()
        release.wait(10)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows mandatory byte-range locks")
def test_coordinator_contention_waits_instead_of_writing_a_locked_byte(tmp_path):
    context = multiprocessing.get_context("spawn")
    ready = context.Event()
    release = context.Event()
    holder = context.Process(target=_hold_coordinator, args=(tmp_path, ready, release))
    holder.start()
    try:
        assert ready.wait(10)
        with pytest.raises(TimeoutError, match="kunci koordinasi"):
            with _coordinator_lock(Settings(data_dir=tmp_path), timeout=0.1):
                pytest.fail("Contended coordinator must not be acquired")
    finally:
        release.set()
        holder.join(10)
        if holder.is_alive():
            holder.terminate()
            holder.join()
    assert holder.exitcode == 0
