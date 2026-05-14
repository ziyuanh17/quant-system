from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

from quant.models.scheduler import (
    ScheduledRunRecord,
    ScheduledRunStatus,
    ScheduledTaskResult,
)

ScheduledTask = Callable[[], ScheduledTaskResult]


class SchedulerRunner:
    """Small finite scheduler loop for repeatable local or server runs."""

    def __init__(self, *, output_dir: Path) -> None:
        self.output_dir = output_dir

    def run_once(
        self, *, task_name: str, task: ScheduledTask
    ) -> ScheduledRunRecord:
        started_at = datetime.now(UTC)
        try:
            result = task()
        except Exception as exc:
            # The scheduler should turn task crashes into run records so a
            # server process can report failures instead of failing silently.
            record = ScheduledRunRecord(
                task_name=task_name,
                status=ScheduledRunStatus.FAILED,
                started_at=started_at,
                message=str(exc),
            )
        else:
            record = ScheduledRunRecord(
                task_name=task_name,
                status=ScheduledRunStatus.SUCCEEDED,
                started_at=started_at,
                message=result.message,
                artifact_paths=result.artifact_paths,
            )

        self.write_run_record(record)
        return record

    def run_loop(
        self,
        *,
        task_name: str,
        task: ScheduledTask,
        iterations: int,
        interval_seconds: float,
    ) -> tuple[ScheduledRunRecord, ...]:
        if iterations < 1:
            raise ValueError("iterations must be at least 1")
        if interval_seconds < 0:
            raise ValueError("interval_seconds must be non-negative")

        records: list[ScheduledRunRecord] = []
        for index in range(iterations):
            records.append(self.run_once(task_name=task_name, task=task))
            is_last_iteration = index == iterations - 1
            if not is_last_iteration and interval_seconds > 0:
                sleep(interval_seconds)
        return tuple(records)

    def write_run_record(self, record: ScheduledRunRecord) -> Path:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        path = self.output_dir / f"{record.run_id}.json"
        path.write_text(record.model_dump_json(indent=2) + "\n")
        return path
