from datetime import UTC, datetime
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
    issues: tuple[HealthIssue, ...] = ()

    @property
    def issue_count(self) -> int:
        return len(self.issues)
