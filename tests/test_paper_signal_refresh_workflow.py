import json

from typer.testing import CliRunner

import quant.cli
from quant.cli import app
from quant.models.ingestion import DataModality, IngestRequest, RawDataset
from quant.models.workflow import WorkflowRunStatus
from quant.operations import FileLock
from quant.workflows import (
    WorkflowRunFailed,
    run_paper_signal_refresh_workflow,
)


def test_paper_signal_refresh_workflow_refreshes_then_runs_signal(
    tmp_path,
) -> None:
    record = run_paper_signal_refresh_workflow(
        provider=FakeTrendingMarketBarProvider(),
        symbol="AAPL",
        start="2024-01-01",
        end="2024-02-01",
        raw_dir=tmp_path / "raw",
        normalized_dir=tmp_path / "normalized",
        validation_dir=tmp_path / "validation",
        metadata_dir=tmp_path / "metadata",
        workflow_output_dir=tmp_path / "workflows",
        strategy="momentum",
        quantity=2,
        initial_cash=1000,
        initial_position_quantity=0,
        initial_position_price=1,
        iterations=1,
        interval_seconds=0,
        min_rows=20,
        signal_output_dir=tmp_path / "signals",
        state_path=tmp_path / "state" / "paper.json",
        run_output_dir=tmp_path / "runs",
        lock_path=tmp_path / "locks" / "workflow.lock",
        lock_stale_after_seconds=60,
    )

    workflow_records = list((tmp_path / "workflows").glob("*.json"))
    signal_records = list((tmp_path / "signals").glob("*.json"))
    scheduler_records = list((tmp_path / "runs").glob("*.json"))

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.normalized_path == str(
        tmp_path / "normalized" / "market_bars" / "AAPL.csv"
    )
    assert len(workflow_records) == 1
    assert len(signal_records) == 1
    assert len(scheduler_records) == 1
    assert (tmp_path / "state" / "paper.json").exists()
    assert not (tmp_path / "locks" / "workflow.lock").exists()
    assert record.scheduler_run_paths == (str(scheduler_records[0]),)
    assert str(signal_records[0]) in record.artifact_paths

    payload = json.loads(signal_records[0].read_text())
    assert payload["decision"]["action"] == "buy"
    assert payload["trade"]["fill"]["quantity"] == 2


def test_paper_signal_refresh_workflow_stops_when_validation_fails(
    tmp_path,
) -> None:
    try:
        run_paper_signal_refresh_workflow(
            provider=BadMarketBarProvider(),
            symbol="AAPL",
            start="2024-01-01",
            end=None,
            raw_dir=tmp_path / "raw",
            normalized_dir=tmp_path / "normalized",
            validation_dir=tmp_path / "validation",
            metadata_dir=tmp_path / "metadata",
            workflow_output_dir=tmp_path / "workflows",
            strategy="momentum",
            quantity=1,
            initial_cash=1000,
            initial_position_quantity=0,
            initial_position_price=1,
            iterations=1,
            interval_seconds=0,
            min_rows=20,
            signal_output_dir=tmp_path / "signals",
            state_path=tmp_path / "state" / "paper.json",
            run_output_dir=tmp_path / "runs",
            lock_path=tmp_path / "locks" / "workflow.lock",
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected failed validation to stop workflow")

    assert record.status == WorkflowRunStatus.FAILED
    assert "validation failed" in record.message
    assert record.validation_report_path is not None
    assert list((tmp_path / "workflows").glob("*.json"))
    assert not (tmp_path / "locks" / "workflow.lock").exists()
    assert not (tmp_path / "signals").exists()
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "state" / "paper.json").exists()


def test_paper_signal_refresh_cli_prints_workflow_record(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "YFinanceMarketBarProvider",
        lambda: FakeTrendingMarketBarProvider(),
    )

    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "paper-signal-refresh",
            "--symbol",
            "AAPL",
            "--start",
            "2024-01-01",
            "--end",
            "2024-02-01",
            "--quantity",
            "2",
            "--initial-cash",
            "1000",
            "--min-rows",
            "20",
            "--raw-dir",
            str(tmp_path / "raw"),
            "--normalized-dir",
            str(tmp_path / "normalized"),
            "--validation-dir",
            str(tmp_path / "validation"),
            "--metadata-dir",
            str(tmp_path / "metadata"),
            "--workflow-output-dir",
            str(tmp_path / "workflows"),
            "--signal-output-dir",
            str(tmp_path / "signals"),
            "--state-path",
            str(tmp_path / "state" / "paper.json"),
            "--run-output-dir",
            str(tmp_path / "runs"),
            "--lock-path",
            str(tmp_path / "locks" / "workflow.lock"),
            "--lock-stale-after-seconds",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Workflow: paper-signal-refresh" in result.output
    assert "Status: succeeded" in result.output
    assert "Scheduler runs: 1" in result.output


def test_paper_signal_refresh_workflow_records_lock_conflict(
    tmp_path,
) -> None:
    lock_path = tmp_path / "locks" / "workflow.lock"
    active_lock = FileLock(
        path=lock_path,
        lock_name="paper-signal-refresh",
        owner="active-run",
        stale_after_seconds=60,
    )
    active_lock.acquire()

    try:
        run_paper_signal_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            symbol="AAPL",
            start="2024-01-01",
            end="2024-02-01",
            raw_dir=tmp_path / "raw",
            normalized_dir=tmp_path / "normalized",
            validation_dir=tmp_path / "validation",
            metadata_dir=tmp_path / "metadata",
            workflow_output_dir=tmp_path / "workflows",
            strategy="momentum",
            quantity=1,
            initial_cash=1000,
            initial_position_quantity=0,
            initial_position_price=1,
            iterations=1,
            interval_seconds=0,
            min_rows=20,
            signal_output_dir=tmp_path / "signals",
            state_path=tmp_path / "state" / "paper.json",
            run_output_dir=tmp_path / "runs",
            lock_path=lock_path,
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected active lock to stop workflow")
    finally:
        active_lock.release()

    assert record.status == WorkflowRunStatus.FAILED
    assert "lock already held" in record.message
    assert record.lock_path == str(lock_path)
    assert not (tmp_path / "raw").exists()


def test_paper_signal_refresh_workflow_releases_lock_after_error(
    tmp_path,
) -> None:
    lock_path = tmp_path / "locks" / "workflow.lock"

    try:
        run_paper_signal_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            symbol="AAPL",
            start="2024-01-01",
            end="2024-02-01",
            raw_dir=tmp_path / "raw",
            normalized_dir=tmp_path / "normalized",
            validation_dir=tmp_path / "validation",
            metadata_dir=tmp_path / "metadata",
            workflow_output_dir=tmp_path / "workflows",
            strategy="unknown",
            quantity=1,
            initial_cash=1000,
            initial_position_quantity=0,
            initial_position_price=1,
            iterations=1,
            interval_seconds=0,
            min_rows=20,
            signal_output_dir=tmp_path / "signals",
            state_path=tmp_path / "state" / "paper.json",
            run_output_dir=tmp_path / "runs",
            lock_path=lock_path,
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed:
        pass
    else:
        raise AssertionError("expected invalid strategy to stop workflow")

    assert not lock_path.exists()


class FakeTrendingMarketBarProvider:
    name = "fake"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        closes = [10.0] * 19 + [8.0] * 5 + [20.0]
        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=[
                {
                    "Date": f"2024-01-{index:02d}",
                    "symbol": "AAPL",
                    "Open": close,
                    "High": close + 1,
                    "Low": close - 1,
                    "Close": close,
                    "Adj Close": close,
                    "Volume": 1000,
                }
                for index, close in enumerate(closes, start=1)
            ],
        )


class BadMarketBarProvider:
    name = "bad"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=[
                {
                    "Date": "2024-01-02",
                    "symbol": "AAPL",
                    "Open": 100.0,
                    "High": 99.0,
                    "Low": 100.0,
                    "Close": 101.0,
                    "Adj Close": 101.0,
                    "Volume": 1000,
                }
            ],
        )
