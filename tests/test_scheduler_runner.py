import json

from quant.models.scheduler import ScheduledRunStatus, ScheduledTaskResult
from quant.scheduler import SchedulerRunner


def test_scheduler_runner_writes_success_record(tmp_path) -> None:
    runner = SchedulerRunner(output_dir=tmp_path)

    record = runner.run_once(
        task_name="sample",
        task=lambda: ScheduledTaskResult(
            message="done",
            artifact_paths=("artifact.json",),
        ),
    )

    path = tmp_path / f"{record.run_id}.json"
    payload = json.loads(path.read_text())
    assert record.status == ScheduledRunStatus.SUCCEEDED
    assert payload["task_name"] == "sample"
    assert payload["message"] == "done"
    assert payload["artifact_paths"] == ["artifact.json"]


def test_scheduler_runner_records_task_failure(tmp_path) -> None:
    runner = SchedulerRunner(output_dir=tmp_path)

    def fail() -> ScheduledTaskResult:
        raise RuntimeError("task exploded")

    record = runner.run_once(task_name="sample", task=fail)

    assert record.status == ScheduledRunStatus.FAILED
    assert record.message == "task exploded"
    assert (tmp_path / f"{record.run_id}.json").exists()


def test_scheduler_runner_rejects_invalid_loop_config(tmp_path) -> None:
    runner = SchedulerRunner(output_dir=tmp_path)

    try:
        runner.run_loop(
            task_name="sample",
            task=lambda: ScheduledTaskResult(message="done"),
            iterations=0,
            interval_seconds=0,
        )
    except ValueError as exc:
        assert str(exc) == "iterations must be at least 1"
    else:
        raise AssertionError("expected invalid iterations to raise")
