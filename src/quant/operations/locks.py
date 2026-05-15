import os
import socket
from pathlib import Path
from uuid import uuid4

from pydantic import ValidationError

from quant.models.operations import RunLockRecord


class LockAcquisitionError(RuntimeError):
    def __init__(self, path: Path, record: RunLockRecord | None) -> None:
        message = f"lock already held: {path}"
        if record is not None:
            message = (
                f"{message} by {record.owner} until "
                f"{record.expires_at.isoformat()}"
            )
        super().__init__(message)
        self.path = path
        self.record = record


class FileLock:
    """Atomic file lock for scheduled local/server workflows."""

    def __init__(
        self,
        *,
        path: Path,
        lock_name: str,
        stale_after_seconds: int,
        owner: str | None = None,
        hostname: str | None = None,
        pid: int | None = None,
    ) -> None:
        if stale_after_seconds <= 0:
            raise ValueError("stale_after_seconds must be positive")
        self.path = path
        self.lock_name = lock_name
        self.stale_after_seconds = stale_after_seconds
        self.hostname = hostname or socket.gethostname()
        self.pid = pid or os.getpid()
        self.owner = owner or _default_owner(lock_name, self.hostname, self.pid)
        self.record: RunLockRecord | None = None

    def acquire(self) -> RunLockRecord:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        record = RunLockRecord(
            lock_name=self.lock_name,
            owner=self.owner,
            hostname=self.hostname,
            pid=self.pid,
            stale_after_seconds=self.stale_after_seconds,
        )
        try:
            self._write_new_lock(record)
        except FileExistsError:
            existing = read_lock_record(self.path)
            if existing is None:
                raise LockAcquisitionError(self.path, existing) from None

            if not existing.is_stale() and not self._is_recoverable(existing):
                raise LockAcquisitionError(self.path, existing) from None

            # Stale locks are removed so a later server run can recover after a
            # crash. The following exclusive create still protects the race.
            self.path.unlink(missing_ok=True)
            try:
                self._write_new_lock(record)
            except FileExistsError:
                raise LockAcquisitionError(
                    self.path,
                    read_lock_record(self.path),
                ) from None

        self.record = record
        return record

    def release(self) -> None:
        if self.record is None:
            return
        existing = read_lock_record(self.path)
        if existing is not None and existing.owner == self.record.owner:
            self.path.unlink(missing_ok=True)
        self.record = None

    def __enter__(self) -> RunLockRecord:
        return self.acquire()

    def __exit__(self, *exc_info: object) -> None:
        self.release()

    def _write_new_lock(self, record: RunLockRecord) -> None:
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        fd = os.open(self.path, flags, 0o644)
        with os.fdopen(fd, "w") as file:
            file.write(record.model_dump_json(indent=2) + "\n")

    def _is_recoverable(self, existing: RunLockRecord) -> bool:
        """Check if the existing lock is from a dead process on the same host."""
        if existing.hostname != self.hostname:
            return False
        return not _is_process_alive(existing.pid)


def read_lock_record(path: Path) -> RunLockRecord | None:
    try:
        return RunLockRecord.model_validate_json(path.read_text())
    except (OSError, ValidationError, ValueError):
        return None


def _is_process_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def _default_owner(lock_name: str, hostname: str, pid: int) -> str:
    return f"{hostname}:{pid}:{lock_name}:{uuid4()}"
