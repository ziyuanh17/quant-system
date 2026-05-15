from datetime import UTC, datetime
from pathlib import Path

from quant.data import ingest_market_bars, load_price_csv
from quant.data.providers.base import DataProvider
from quant.execution import (
    PaperBroker,
    execute_latest_signal,
    load_paper_broker_state,
    save_paper_broker_state,
    write_paper_signal_record,
)
from quant.models.execution import Position
from quant.models.ingestion import IngestArtifactPaths, IngestRequest
from quant.models.scheduler import ScheduledRunRecord, ScheduledTaskResult
from quant.models.workflow import DataRefreshWorkflowRecord, WorkflowRunStatus
from quant.scheduler import SchedulerRunner
from quant.strategies import MomentumStrategy


class WorkflowRunFailed(RuntimeError):
    def __init__(self, record: DataRefreshWorkflowRecord) -> None:
        super().__init__(record.message)
        self.record = record


def run_paper_signal_refresh_workflow(
    *,
    provider: DataProvider,
    symbol: str,
    start: str,
    end: str | None,
    raw_dir: Path,
    normalized_dir: Path,
    validation_dir: Path,
    metadata_dir: Path,
    workflow_output_dir: Path,
    strategy: str,
    quantity: int,
    initial_cash: float,
    initial_position_quantity: int,
    initial_position_price: float,
    iterations: int,
    interval_seconds: float,
    min_rows: int,
    signal_output_dir: Path,
    state_path: Path,
    run_output_dir: Path,
) -> DataRefreshWorkflowRecord:
    """Refresh data, validate it, then run the paper-signal scheduler."""
    started_at = datetime.now(UTC)
    ingest_artifact: IngestArtifactPaths | None = None
    scheduler_records: tuple[ScheduledRunRecord, ...] = ()

    try:
        if strategy != "momentum":
            raise ValueError("Only momentum is implemented right now.")

        request = IngestRequest(symbols=(symbol,), start=start, end=end)
        artifacts = ingest_market_bars(
            provider,
            request,
            raw_root=raw_dir,
            normalized_root=normalized_dir,
            validation_root=validation_dir,
            metadata_root=metadata_dir,
            validate=True,
            min_rows=min_rows,
        )
        ingest_artifact = _single_artifact(artifacts)
        if ingest_artifact.validation_passed is not True:
            raise ValueError(
                "data refresh validation failed; paper signal was not run"
            )

        scheduler_records = _run_paper_signal_loop(
            data=Path(ingest_artifact.normalized_path),
            symbol=symbol,
            quantity=quantity,
            initial_cash=initial_cash,
            initial_position_quantity=initial_position_quantity,
            initial_position_price=initial_position_price,
            iterations=iterations,
            interval_seconds=interval_seconds,
            signal_output_dir=signal_output_dir,
            state_path=state_path,
            run_output_dir=run_output_dir,
        )
        failed_runs = [
            record
            for record in scheduler_records
            if record.status.value == "failed"
        ]
        if failed_runs:
            message = f"{len(failed_runs)} paper signal scheduler runs failed"
            status = WorkflowRunStatus.FAILED
        else:
            message = "data refreshed and paper signal workflow completed"
            status = WorkflowRunStatus.SUCCEEDED

        record = _build_record(
            status=status,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=message,
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        if status == WorkflowRunStatus.FAILED:
            raise WorkflowRunFailed(record)
        return record
    except WorkflowRunFailed:
        raise
    except Exception as exc:
        record = _build_record(
            status=WorkflowRunStatus.FAILED,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=str(exc),
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        raise WorkflowRunFailed(record) from exc


def write_data_refresh_workflow_record(
    record: DataRefreshWorkflowRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.workflow_id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def _run_paper_signal_loop(
    *,
    data: Path,
    symbol: str,
    quantity: int,
    initial_cash: float,
    initial_position_quantity: int,
    initial_position_price: float,
    iterations: int,
    interval_seconds: float,
    signal_output_dir: Path,
    state_path: Path,
    run_output_dir: Path,
) -> tuple[ScheduledRunRecord, ...]:
    initial_positions = _initial_positions(
        symbol=symbol,
        quantity=initial_position_quantity,
        price=initial_position_price,
    )
    state = load_paper_broker_state(
        state_path,
        default_cash=initial_cash,
        default_positions=initial_positions,
    )
    broker = PaperBroker.from_state(state)
    runner = SchedulerRunner(output_dir=run_output_dir)
    strategy = MomentumStrategy()

    def task() -> ScheduledTaskResult:
        # The workflow has already refreshed and validated this normalized file.
        # Reloading inside each attempt matches the scheduler v1 behavior.
        prices = load_price_csv(data, symbol)
        record = execute_latest_signal(
            strategy=strategy,
            prices=prices,
            broker=broker,
            quantity=quantity,
        )
        signal_path = write_paper_signal_record(record, signal_output_dir)
        state_path_written = save_paper_broker_state(
            broker.state(), state_path
        )
        message = f"paper signal {record.decision.action}"
        if record.skipped:
            message = f"{message}: skipped duplicate"
        if record.trade is not None and record.trade.order.risk.reason:
            message = f"{message}: {record.trade.order.risk.reason}"
        return ScheduledTaskResult(
            message=message,
            artifact_paths=(str(signal_path), str(state_path_written)),
        )

    return runner.run_loop(
        task_name="paper-signal",
        task=task,
        iterations=iterations,
        interval_seconds=interval_seconds,
    )


def _initial_positions(
    *,
    symbol: str,
    quantity: int,
    price: float,
) -> tuple[Position, ...]:
    if quantity == 0:
        return ()
    return (
        Position(
            symbol=symbol,
            quantity=quantity,
            average_price=price,
            last_price=price,
        ),
    )


def _single_artifact(
    artifacts: list[IngestArtifactPaths],
) -> IngestArtifactPaths:
    if len(artifacts) != 1:
        raise ValueError("paper signal refresh expects exactly one symbol")
    return artifacts[0]


def _build_record(
    *,
    status: WorkflowRunStatus,
    started_at: datetime,
    provider: str,
    symbol: str,
    start: str,
    end: str | None,
    message: str,
    ingest_artifact: IngestArtifactPaths | None,
    scheduler_records: tuple[ScheduledRunRecord, ...],
    run_output_dir: Path,
) -> DataRefreshWorkflowRecord:
    scheduler_run_paths = tuple(
        str(run_output_dir / f"{record.run_id}.json")
        for record in scheduler_records
    )
    artifact_paths = _artifact_paths(
        ingest_artifact=ingest_artifact,
        scheduler_run_paths=scheduler_run_paths,
        scheduler_records=scheduler_records,
    )
    return DataRefreshWorkflowRecord(
        status=status,
        started_at=started_at,
        provider=provider,
        symbol=symbol,
        request_start=start,
        request_end=end,
        message=message,
        raw_path=ingest_artifact.raw_path if ingest_artifact else None,
        normalized_path=(
            ingest_artifact.normalized_path if ingest_artifact else None
        ),
        validation_report_path=(
            ingest_artifact.validation_report_path
            if ingest_artifact
            else None
        ),
        metadata_path=(
            ingest_artifact.metadata_path if ingest_artifact else None
        ),
        scheduler_run_paths=scheduler_run_paths,
        artifact_paths=artifact_paths,
    )


def _artifact_paths(
    *,
    ingest_artifact: IngestArtifactPaths | None,
    scheduler_run_paths: tuple[str, ...],
    scheduler_records: tuple[ScheduledRunRecord, ...],
) -> tuple[str, ...]:
    paths: list[str] = []
    if ingest_artifact is not None:
        paths.extend(
            path
            for path in (
                ingest_artifact.raw_path,
                ingest_artifact.normalized_path,
                ingest_artifact.validation_report_path,
                ingest_artifact.metadata_path,
            )
            if path is not None
        )
    paths.extend(scheduler_run_paths)
    for record in scheduler_records:
        paths.extend(record.artifact_paths)
    return tuple(paths)
