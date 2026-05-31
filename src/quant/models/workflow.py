from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from quant.models.base import FrozenModel


class WorkflowRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class DataRefreshWorkflowRecord(FrozenModel):
    """Audit record for one refresh-then-paper-signal workflow attempt."""

    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_name: str = "paper-signal-refresh"
    status: WorkflowRunStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    symbol: str
    request_start: str
    request_end: str | None = None
    message: str
    raw_path: str | None = None
    normalized_path: str | None = None
    validation_report_path: str | None = None
    metadata_path: str | None = None
    lock_path: str | None = None
    lock_owner: str | None = None
    scheduler_run_paths: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    latest_signal_action: str | None = None
    latest_signal_reason: str | None = None
    latest_signal_market_price: float | None = None
    broker_submission_attempted: bool | None = None
    broker_submission_skipped_reason: str | None = None
    order_artifact_paths: tuple[str, ...] = ()
    fill_artifact_paths: tuple[str, ...] = ()
    snapshot_artifact_paths: tuple[str, ...] = ()
    reconciliation_report_path: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
