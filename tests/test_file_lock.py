import socket
from datetime import UTC, datetime, timedelta

from quant.models.operations import RunLockRecord
from quant.operations import FileLock, LockAcquisitionError, read_lock_record


def test_file_lock_creates_and_releases_lock_file(tmp_path) -> None:
    path = tmp_path / "locks" / "workflow.lock"

    with FileLock(
        path=path,
        lock_name="workflow",
        owner="test-owner",
        stale_after_seconds=60,
    ) as record:
        assert path.exists()
        assert record.owner == "test-owner"
        assert read_lock_record(path) == record

    assert not path.exists()


def test_file_lock_rejects_active_lock(tmp_path) -> None:
    path = tmp_path / "workflow.lock"
    first = FileLock(
        path=path,
        lock_name="workflow",
        owner="first",
        stale_after_seconds=60,
    )
    first.acquire()

    try:
        FileLock(
            path=path,
            lock_name="workflow",
            owner="second",
            stale_after_seconds=60,
        ).acquire()
    except LockAcquisitionError as exc:
        assert exc.record is not None
        assert exc.record.owner == "first"
    else:
        raise AssertionError("expected active lock to block acquisition")
    finally:
        first.release()


def test_file_lock_replaces_stale_lock(tmp_path) -> None:
    path = tmp_path / "workflow.lock"
    stale_record = RunLockRecord(
        lock_name="workflow",
        owner="stale-owner",
        hostname="other-host",
        pid=12345,
        acquired_at=datetime.now(UTC) - timedelta(seconds=120),
        stale_after_seconds=60,
    )
    path.write_text(stale_record.model_dump_json())

    with FileLock(
        path=path,
        lock_name="workflow",
        owner="fresh-owner",
        stale_after_seconds=60,
    ) as record:
        assert record.owner == "fresh-owner"
        assert read_lock_record(path) == record


def test_file_lock_replaces_dead_pid_lock(tmp_path) -> None:
    path = tmp_path / "workflow.lock"
    # 999999 is unlikely to be a running PID on most systems
    dead_record = RunLockRecord(
        lock_name="workflow",
        owner="dead-owner",
        hostname=socket.gethostname(),
        pid=999999,
        stale_after_seconds=60,
    )
    path.write_text(dead_record.model_dump_json())

    with FileLock(
        path=path,
        lock_name="workflow",
        owner="fresh-owner",
        stale_after_seconds=60,
    ) as record:
        assert record.owner == "fresh-owner"
        assert read_lock_record(path) == record

