from datetime import UTC, datetime, timedelta
from enum import StrEnum

from pydantic import Field

from quant.models.base import FrozenModel


class HealthStatus(StrEnum):
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class HealthIssueSeverity(StrEnum):
    WARNING = "warning"
    ERROR = "error"


class HealthIssue(FrozenModel):
    code: str
    severity: HealthIssueSeverity
    message: str


class HealthReport(FrozenModel):
    """Read-only operational summary for the local quant service."""

    status: HealthStatus
    checked_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    run_records_dir: str
    signal_records_dir: str
    state_path: str
    logs_dir: str
    latest_run_path: str | None = None
    latest_run_status: str | None = None
    latest_run_completed_at: datetime | None = None
    latest_signal_path: str | None = None
    latest_signal_action: str | None = None
    latest_signal_date: str | None = None
    latest_signal_skipped: bool | None = None
    state_cash: float | None = None
    state_position_count: int | None = None
    log_count: int = 0
    lock_path: str | None = None
    lock_status: str = "not_checked"
    lock_owner: str | None = None
    lock_expires_at: datetime | None = None
    reconciliation_status: str = "skipped"
    reconciliation_difference_count: int | None = None
    reconciliation_report_path: str | None = None
    issues: tuple[HealthIssue, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)


class RunLockRecord(FrozenModel):
    """On-disk record for a single active operational lock."""

    lock_name: str
    owner: str
    hostname: str
    pid: int
    acquired_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stale_after_seconds: int = Field(gt=0)

    @property
    def expires_at(self) -> datetime:
        return self.acquired_at + timedelta(seconds=self.stale_after_seconds)

    def is_stale(self, now: datetime | None = None) -> bool:
        checked_at = now or datetime.now(UTC)
        return checked_at >= self.expires_at
