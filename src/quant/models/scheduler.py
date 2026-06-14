"""Define domain models for scheduled task execution."""

from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from quant.models.base import FrozenModel


class ScheduledRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class ScheduledTaskResult(FrozenModel):
    message: str
    artifact_paths: tuple[str, ...] = ()


class ScheduledRunRecord(FrozenModel):
    """Durable audit record for one scheduled task attempt."""

    run_id: str = Field(default_factory=lambda: str(uuid4()))
    task_name: str
    status: ScheduledRunStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    message: str
    artifact_paths: tuple[str, ...] = ()

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
