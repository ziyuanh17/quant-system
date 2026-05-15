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
    scheduler_run_paths: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
