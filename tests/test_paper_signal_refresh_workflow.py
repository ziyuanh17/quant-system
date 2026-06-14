"""Test paper signal refresh workflow behavior and safety invariants."""

import json

from typer.testing import CliRunner

import quant.cli
from quant.cli import app
from quant.execution import LIVE_TRADING_CONFIRMATION, PaperBroker
from quant.execution.artifacts import (
    write_live_account_snapshot,
    write_live_fill_record,
    write_live_order_record,
    write_paper_signal_record,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
    Position,
    ShortSellingPolicy,
    TradingMode,
    TradingSafetyCheck,
    TradingSafetyConfig,
)
from quant.models.ingestion import DataModality, IngestRequest, RawDataset
from quant.models.workflow import WorkflowRunStatus
from quant.operations import FileLock
from quant.workflows import (
    WorkflowRunFailed,
    run_alpaca_paper_refresh_workflow,
    run_dry_run_refresh_workflow,
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


def test_dry_run_refresh_workflow_refreshes_runs_and_compares(
    tmp_path,
) -> None:
    paper_signal_dir = tmp_path / "paper" / "signals"
    _write_matching_paper_signal(paper_signal_dir, quantity=2, price=20)

    record = run_dry_run_refresh_workflow(
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
        broker_name="dry-run",
        iterations=1,
        interval_seconds=0,
        min_rows=20,
        dry_run_output_dir=tmp_path / "dry_run" / "orders",
        run_output_dir=tmp_path / "runs" / "dry-run",
        paper_signal_dir=paper_signal_dir,
        comparison_output_path=tmp_path
        / "dry_run"
        / "comparison"
        / "latest.json",
        publish_status_path=tmp_path / "site" / "status.json",
        paper_state_path=tmp_path / "paper" / "state.json",
        logs_dir=tmp_path / "logs",
        lock_path=tmp_path / "locks" / "dry-run.lock",
        lock_stale_after_seconds=60,
    )

    dry_run_records = list((tmp_path / "dry_run" / "orders").glob("*.json"))
    scheduler_records = list((tmp_path / "runs" / "dry-run").glob("*.json"))
    comparison_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    status_path = tmp_path / "site" / "status.json"

    assert record.workflow_name == "dry-run-refresh"
    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert len(dry_run_records) == 1
    assert len(scheduler_records) == 1
    assert comparison_path.exists()
    assert status_path.exists()
    assert str(comparison_path) in record.artifact_paths
    assert str(status_path) in record.artifact_paths
    assert not (tmp_path / "paper" / "state.json").exists()
    assert not (tmp_path / "locks" / "dry-run.lock").exists()


def test_dry_run_refresh_workflow_stops_when_validation_fails(
    tmp_path,
) -> None:
    try:
        run_dry_run_refresh_workflow(
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
            broker_name="dry-run",
            iterations=1,
            interval_seconds=0,
            min_rows=20,
            dry_run_output_dir=tmp_path / "dry_run" / "orders",
            run_output_dir=tmp_path / "runs" / "dry-run",
            paper_signal_dir=tmp_path / "paper" / "signals",
            comparison_output_path=tmp_path
            / "dry_run"
            / "comparison"
            / "latest.json",
            lock_path=tmp_path / "locks" / "dry-run.lock",
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected failed validation to stop workflow")

    assert record.workflow_name == "dry-run-refresh"
    assert record.status == WorkflowRunStatus.FAILED
    assert "validation failed" in record.message
    assert not (tmp_path / "dry_run").exists()
    assert not (tmp_path / "runs").exists()
    assert not (tmp_path / "locks" / "dry-run.lock").exists()


def test_dry_run_refresh_cli_prints_workflow_record(
    tmp_path,
    monkeypatch,
) -> None:
    paper_signal_dir = tmp_path / "paper" / "signals"
    _write_matching_paper_signal(paper_signal_dir, quantity=2, price=20)
    monkeypatch.setattr(
        quant.cli,
        "YFinanceMarketBarProvider",
        lambda: FakeTrendingMarketBarProvider(),
    )

    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "dry-run-refresh",
            "--symbol",
            "AAPL",
            "--start",
            "2024-01-01",
            "--end",
            "2024-02-01",
            "--quantity",
            "2",
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
            "--dry-run-output-dir",
            str(tmp_path / "dry_run" / "orders"),
            "--run-output-dir",
            str(tmp_path / "runs" / "dry-run"),
            "--paper-signal-dir",
            str(paper_signal_dir),
            "--comparison-output-path",
            str(tmp_path / "dry_run" / "comparison" / "latest.json"),
            "--lock-path",
            str(tmp_path / "locks" / "dry-run.lock"),
            "--lock-stale-after-seconds",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Workflow: dry-run-refresh" in result.output
    assert "Status: succeeded" in result.output
    assert "Scheduler runs: 1" in result.output


def test_alpaca_paper_refresh_workflow_submits_and_reconciles(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeTrendingMarketBarProvider(),
        broker_client=client,
        safety_config=TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=1000,
            broker_name="alpaca-paper",
        ),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
        lock_path=tmp_path / "locks" / "alpaca-paper-refresh.lock",
        lock_stale_after_seconds=60,
    )

    order_paths = list((tmp_path / "live" / "orders").glob("*.json"))
    fill_paths = list((tmp_path / "live" / "fills").glob("*.json"))
    snapshot_paths = list((tmp_path / "live" / "snapshots").glob("*.json"))
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"

    assert record.workflow_name == "alpaca-paper-refresh"
    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.message == (
        "data refreshed and Alpaca paper workflow completed"
    )
    assert len(order_paths) == 1
    assert len(fill_paths) == 1
    assert len(snapshot_paths) == 1
    assert reconciliation_path.exists()
    assert str(reconciliation_path) in record.artifact_paths
    assert record.latest_signal_action == "buy"
    assert record.latest_signal_reason == "latest strategy signal is entry"
    assert record.latest_signal_market_price == 20.0
    assert record.broker_submission_attempted is True
    assert record.broker_submission_skipped_reason is None
    assert record.broker_position_quantity_before == 0
    assert record.strategy_target_quantity == 2
    assert record.planned_order_side == "buy"
    assert record.planned_order_quantity == 2
    assert record.order_artifact_paths == tuple(
        str(path) for path in order_paths
    )
    assert record.fill_artifact_paths == tuple(str(path) for path in fill_paths)
    assert record.snapshot_artifact_paths == tuple(
        str(path) for path in snapshot_paths
    )
    assert record.reconciliation_report_path == str(reconciliation_path)
    assert not (tmp_path / "locks" / "alpaca-paper-refresh.lock").exists()
    assert client.submitted_client_order_ids == (
        "momentum:AAPL:2024-01-25:buy",
    )


def test_alpaca_paper_refresh_workflow_records_hold_without_order(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeFlatMarketBarProvider(),
        broker_client=client,
        safety_config=TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=True,
            live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
            max_order_notional=1000,
            broker_name="alpaca-paper",
        ),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
        lock_path=tmp_path / "locks" / "alpaca-paper-refresh.lock",
        lock_stale_after_seconds=60,
    )

    assert client.submitted_client_order_ids == ()
    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.latest_signal_action == "hold"
    assert record.latest_signal_reason == "latest strategy signal is hold"
    assert record.latest_signal_market_price == 10.0
    assert record.broker_submission_attempted is False
    assert (
        record.broker_submission_skipped_reason
        == "latest strategy signal is hold"
    )
    assert record.order_artifact_paths == ()
    assert record.fill_artifact_paths == ()
    assert record.broker_position_quantity_before == 0
    assert record.strategy_target_quantity == 0
    assert record.planned_order_side is None
    assert record.planned_order_quantity is None
    assert len(record.snapshot_artifact_paths) == 1
    assert record.reconciliation_report_path == str(
        tmp_path / "live" / "reconciliation" / "latest.json"
    )
    assert not (tmp_path / "locks" / "alpaca-paper-refresh.lock").exists()


def test_alpaca_paper_refresh_hold_remembers_durable_orders_before_reconcile(
    tmp_path,
) -> None:
    client = DurableOrderContextWorkflowClient()
    order_dir = tmp_path / "live" / "orders"
    fill_dir = tmp_path / "live" / "fills"
    snapshot_dir = tmp_path / "live" / "snapshots"
    write_live_order_record(client.historical_order, order_dir)
    write_live_fill_record(client.historical_fill, fill_dir)
    write_live_account_snapshot(client.account_snapshot(), snapshot_dir)

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeFlatMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=order_dir,
        fill_output_dir=fill_dir,
        snapshot_output_dir=snapshot_dir,
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.latest_signal_action == "hold"
    assert client.remembered_client_order_ids == ("historical-order",)


def test_alpaca_paper_refresh_workflow_exit_from_flat_submits_no_order(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeFallingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.broker_submission_attempted is False
    assert (
        record.broker_submission_skipped_reason
        == "strategy target position is already satisfied"
    )
    assert client.submitted_client_order_ids == ()
    assert record.broker_position_quantity_before == 0
    assert record.strategy_target_quantity == 0


def test_alpaca_paper_refresh_workflow_entry_reverses_short_to_long_target(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient(initial_positions={"AAPL": -1})

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeTrendingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert len(client.submitted_client_order_ids) == 1
    assert record.broker_position_quantity_before == -1
    assert record.strategy_target_quantity == 1
    assert record.planned_order_side == "buy"
    assert record.planned_order_quantity == 2
    assert client._orders[0].request.side == OrderSide.BUY
    assert client._orders[0].request.quantity == 2
    assert client.account_snapshot().positions[0].quantity == 1


def test_alpaca_paper_refresh_reversal_checks_full_delta_notional(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient(initial_positions={"AAPL": -1})

    try:
        run_alpaca_paper_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            broker_client=client,
            safety_config=TradingSafetyConfig(
                mode=TradingMode.LIVE,
                live_trading_enabled=True,
                live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
                max_order_notional=30,
                broker_name="alpaca-paper",
            ),
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
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=tmp_path
            / "live"
            / "reconciliation"
            / "latest.json",
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected full reversal delta to exceed order cap")

    assert record.status == WorkflowRunStatus.FAILED
    assert "order notional exceeds max_order_notional" in record.message
    assert client.submitted_client_order_ids == ()


def test_alpaca_paper_refresh_repeated_entry_at_target_submits_no_order(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient(initial_positions={"AAPL": 1})

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeTrendingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert record.broker_submission_attempted is False
    assert (
        record.broker_submission_skipped_reason
        == "strategy target position is already satisfied"
    )
    assert client.submitted_client_order_ids == ()


def test_alpaca_paper_refresh_exit_covers_short_without_borrow_check(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient(initial_positions={"AAPL": -1})
    client.asset_easy_to_borrow = False

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeFallingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert client._orders[0].request.side == OrderSide.BUY
    assert client._orders[0].request.quantity == 1
    assert client.account_snapshot().positions == ()


def test_alpaca_paper_refresh_exit_closes_long_target_to_flat(tmp_path) -> None:
    client = FakeAlpacaPaperWorkflowClient(initial_positions={"AAPL": 2})

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeFallingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
    )

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert client._orders[0].request.side == OrderSide.SELL
    assert client._orders[0].request.quantity == 2
    assert client.account_snapshot().positions == ()


def test_alpaca_paper_refresh_workflow_rejects_submission_with_open_order(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()
    client.existing_open_orders = (
        LiveOrderRecord(
            client_order_id="existing-open-order",
            broker_order_id="alpaca-order-existing",
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            request=OrderRequest(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=1,
            ),
            reference_price=100,
            notional=100,
            safety_check=TradingSafetyCheck(
                mode=TradingMode.LIVE,
                allowed=True,
            ),
            status=LiveOrderStatus.ACCEPTED,
        ),
    )

    try:
        run_alpaca_paper_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            broker_client=client,
            safety_config=_alpaca_paper_safety_config(),
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
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=tmp_path
            / "live"
            / "reconciliation"
            / "latest.json",
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected open broker order to block submission")

    assert record.status == WorkflowRunStatus.FAILED
    assert "open broker order" in record.message
    assert client.submitted_client_order_ids == ()


def test_alpaca_paper_refresh_workflow_refreshes_order_before_reconcile(
    tmp_path,
) -> None:
    client = DelayedFillAlpacaPaperWorkflowClient()

    record = run_alpaca_paper_refresh_workflow(
        provider=FakeTrendingMarketBarProvider(),
        broker_client=client,
        safety_config=_alpaca_paper_safety_config(),
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
        min_rows=20,
        order_output_dir=tmp_path / "live" / "orders",
        fill_output_dir=tmp_path / "live" / "fills",
        snapshot_output_dir=tmp_path / "live" / "snapshots",
        reconciliation_output_path=tmp_path
        / "live"
        / "reconciliation"
        / "latest.json",
        order_poll_attempts=2,
        order_poll_interval_seconds=0,
    )

    order_path = next((tmp_path / "live" / "orders").glob("*.json"))
    order_payload = json.loads(order_path.read_text())
    fill_paths = list((tmp_path / "live" / "fills").glob("*.json"))

    assert record.status == WorkflowRunStatus.SUCCEEDED
    assert client.refresh_calls == 1
    assert order_payload["status"] == "filled"
    assert len(fill_paths) == 1
    assert len(record.fill_artifact_paths) == 1


def test_alpaca_paper_refresh_workflow_fails_when_refreshed_order_is_cancelled(
    tmp_path,
) -> None:
    client = CancelledAlpacaPaperWorkflowClient()

    try:
        run_alpaca_paper_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            broker_client=client,
            safety_config=_alpaca_paper_safety_config(),
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
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=tmp_path
            / "live"
            / "reconciliation"
            / "latest.json",
            order_poll_attempts=2,
            order_poll_interval_seconds=0,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected cancelled actionable order to fail")

    assert record.status == WorkflowRunStatus.FAILED
    assert "ended with status cancelled" in record.message


def test_alpaca_paper_refresh_workflow_stops_before_broker_on_validation_error(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()

    try:
        run_alpaca_paper_refresh_workflow(
            provider=BadMarketBarProvider(),
            broker_client=client,
            safety_config=TradingSafetyConfig(
                mode=TradingMode.LIVE,
                live_trading_enabled=True,
                live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
                max_order_notional=1000,
                broker_name="alpaca-paper",
            ),
            symbol="AAPL",
            start="2024-01-01",
            end=None,
            raw_dir=tmp_path / "raw",
            normalized_dir=tmp_path / "normalized",
            validation_dir=tmp_path / "validation",
            metadata_dir=tmp_path / "metadata",
            workflow_output_dir=tmp_path / "workflows",
            strategy="momentum",
            quantity=2,
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=tmp_path
            / "live"
            / "reconciliation"
            / "latest.json",
            lock_path=tmp_path / "locks" / "alpaca-paper-refresh.lock",
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected failed validation to stop workflow")

    assert record.workflow_name == "alpaca-paper-refresh"
    assert record.status == WorkflowRunStatus.FAILED
    assert "validation failed" in record.message
    assert client.submitted_client_order_ids == ()
    assert not (tmp_path / "live").exists()
    assert not (tmp_path / "locks" / "alpaca-paper-refresh.lock").exists()


def test_alpaca_paper_refresh_workflow_records_lock_conflict(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient()
    lock_path = tmp_path / "locks" / "alpaca-paper-refresh.lock"
    active_lock = FileLock(
        path=lock_path,
        lock_name="alpaca-paper-refresh",
        owner="active-run",
        stale_after_seconds=60,
    )
    active_lock.acquire()

    try:
        run_alpaca_paper_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            broker_client=client,
            safety_config=TradingSafetyConfig(
                mode=TradingMode.LIVE,
                live_trading_enabled=True,
                live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
                max_order_notional=1000,
                broker_name="alpaca-paper",
            ),
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
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=tmp_path
            / "live"
            / "reconciliation"
            / "latest.json",
            lock_path=lock_path,
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected active lock to stop workflow")
    finally:
        active_lock.release()

    assert record.workflow_name == "alpaca-paper-refresh"
    assert record.status == WorkflowRunStatus.FAILED
    assert "lock already held" in record.message
    assert client.submitted_client_order_ids == ()
    assert not (tmp_path / "raw").exists()


def test_alpaca_paper_refresh_workflow_fails_on_reconciliation_drift(
    tmp_path,
) -> None:
    client = FakeAlpacaPaperWorkflowClient(drop_broker_fills=True)
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"

    try:
        run_alpaca_paper_refresh_workflow(
            provider=FakeTrendingMarketBarProvider(),
            broker_client=client,
            safety_config=TradingSafetyConfig(
                mode=TradingMode.LIVE,
                live_trading_enabled=True,
                live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
                max_order_notional=1000,
                broker_name="alpaca-paper",
            ),
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
            min_rows=20,
            order_output_dir=tmp_path / "live" / "orders",
            fill_output_dir=tmp_path / "live" / "fills",
            snapshot_output_dir=tmp_path / "live" / "snapshots",
            reconciliation_output_path=reconciliation_path,
            lock_path=tmp_path / "locks" / "alpaca-paper-refresh.lock",
            lock_stale_after_seconds=60,
        )
    except WorkflowRunFailed as exc:
        record = exc.record
    else:
        raise AssertionError("expected reconciliation drift to stop workflow")

    assert record.workflow_name == "alpaca-paper-refresh"
    assert record.status == WorkflowRunStatus.FAILED
    assert "reconciliation failed" in record.message
    assert reconciliation_path.exists()
    assert str(reconciliation_path) in record.artifact_paths


def test_alpaca_paper_refresh_cli_prints_workflow_record(
    tmp_path,
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "YFinanceMarketBarProvider",
        lambda: FakeTrendingMarketBarProvider(),
    )
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperWorkflowClient,
    )
    monkeypatch.setenv("QUANT_ALPACA_PAPER_API_KEY", "paper-key")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", "acct-1")

    result = CliRunner().invoke(
        app,
        [
            "workflow",
            "alpaca-paper-refresh",
            "--symbol",
            "AAPL",
            "--start",
            "2024-01-01",
            "--end",
            "2024-02-01",
            "--quantity",
            "2",
            "--min-rows",
            "20",
            "--live-trading-enabled",
            "--live-trading-confirmation",
            LIVE_TRADING_CONFIRMATION,
            "--max-order-notional",
            "1000",
            "--broker-name",
            "alpaca-paper",
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
            "--order-output-dir",
            str(tmp_path / "live" / "orders"),
            "--fill-output-dir",
            str(tmp_path / "live" / "fills"),
            "--snapshot-output-dir",
            str(tmp_path / "live" / "snapshots"),
            "--reconciliation-output-path",
            str(tmp_path / "live" / "reconciliation" / "latest.json"),
            "--lock-path",
            str(tmp_path / "locks" / "alpaca-paper-refresh.lock"),
            "--lock-stale-after-seconds",
            "60",
        ],
    )

    assert result.exit_code == 0
    assert "Workflow: alpaca-paper-refresh" in result.output
    assert "Status: succeeded" in result.output
    assert "Scheduler runs: 0" in result.output


def _write_matching_paper_signal(
    output_dir,
    *,
    quantity: int,
    price: float,
) -> None:
    broker = PaperBroker(initial_cash=1_000)
    trade = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=quantity),
        market_price=price,
    )
    record = PaperSignalRecord(
        decision=PaperSignalDecision(
            symbol="AAPL",
            action=PaperSignalAction.BUY,
            signal_date="2024-01-25",
            market_price=price,
            reason="entry signal",
            idempotency_key="momentum:AAPL:2024-01-25:buy",
        ),
        trade=trade,
        snapshot=trade.snapshot,
    )
    write_paper_signal_record(record, output_dir)


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


class FakeFlatMarketBarProvider:
    name = "fake-flat"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=[
                {
                    "Date": f"2024-01-{index:02d}",
                    "symbol": "AAPL",
                    "Open": 10.0,
                    "High": 11.0,
                    "Low": 9.0,
                    "Close": 10.0,
                    "Adj Close": 10.0,
                    "Volume": 1000,
                }
                for index in range(1, 26)
            ],
        )


class FakeFallingMarketBarProvider:
    name = "fake-falling"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        closes = [20.0] * 19 + [22.0] * 5 + [8.0]
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


class FakeAlpacaPaperWorkflowClient:
    """Immediate-fill Alpaca-paper test double for workflow tests."""

    def __init__(
        self,
        *,
        config=None,
        drop_broker_fills: bool = False,
        initial_positions: dict[str, int] | None = None,
    ) -> None:
        self.config = config
        self.drop_broker_fills = drop_broker_fills
        self.submitted_client_order_ids: tuple[str, ...] = ()
        self._orders: list[LiveOrderRecord] = []
        self._fills: list[LiveFillRecord] = []
        self._fill_calls = 0
        self._cash = 1000.0
        self._positions = {
            symbol: Position(
                symbol=symbol,
                quantity=quantity,
                average_price=10,
                last_price=20,
            )
            for symbol, quantity in (initial_positions or {}).items()
        }
        self.existing_open_orders: tuple[LiveOrderRecord, ...] = ()
        self.asset_easy_to_borrow = True

    def submit_market_order(
        self,
        request,
        *,
        reference_price,
        client_order_id,
        safety_check,
    ) -> LiveOrderRecord:
        self.submitted_client_order_ids = (
            *self.submitted_client_order_ids,
            client_order_id,
        )
        record = LiveOrderRecord(
            client_order_id=client_order_id,
            broker_order_id=f"alpaca-order-{len(self._orders) + 1}",
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            request=request,
            reference_price=reference_price,
            notional=request.quantity * reference_price,
            safety_check=safety_check,
            status=LiveOrderStatus.FILLED,
            raw_response_ref="alpaca-paper:workflow-test-order",
        )
        fill = LiveFillRecord(
            order_record_id=record.id,
            client_order_id=client_order_id,
            broker_order_id=record.broker_order_id or client_order_id,
            broker_execution_id=f"alpaca-exec-{len(self._fills) + 1}",
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=reference_price,
            raw_response_ref="alpaca-paper:workflow-test-fill",
        )
        self._orders.append(record)
        self._fills.append(fill)
        self._apply_fill(fill)
        return record

    def account_snapshot(self) -> LiveAccountSnapshot:
        return LiveAccountSnapshot(
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            cash=self._cash,
            buying_power=self._cash,
            positions=tuple(self._positions.values()),
        )

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        return self.existing_open_orders

    def has_open_orders(self) -> bool:
        return bool(self.existing_open_orders)

    def asset_trading_details(self, symbol: str):
        from quant.models.execution import AssetTradingDetails

        return AssetTradingDetails(
            symbol=symbol,
            tradable=True,
            shortable=True,
            easy_to_borrow=self.asset_easy_to_borrow,
        )

    def fills(self) -> tuple[LiveFillRecord, ...]:
        self._fill_calls += 1
        if self.drop_broker_fills and self._fill_calls > 1:
            return ()
        return tuple(self._fills)

    def remember_order_record(self, record: LiveOrderRecord) -> None:
        return None

    def _apply_fill(self, fill: LiveFillRecord) -> None:
        signed_fill_quantity = (
            fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
        )
        if fill.side == OrderSide.BUY:
            self._cash -= fill.notional
        else:
            self._cash += fill.notional
        existing = self._positions.get(fill.symbol)
        new_quantity = (
            signed_fill_quantity
            if existing is None
            else existing.quantity + signed_fill_quantity
        )
        if new_quantity == 0:
            self._positions.pop(fill.symbol, None)
            return
        self._positions[fill.symbol] = Position(
            symbol=fill.symbol,
            quantity=new_quantity,
            average_price=fill.price,
            last_price=fill.price,
        )

    def refresh_order_record(
        self,
        record: LiveOrderRecord,
    ) -> LiveOrderRecord:
        return record


class DurableOrderContextWorkflowClient(FakeAlpacaPaperWorkflowClient):
    def __init__(self) -> None:
        super().__init__()
        self.remembered_client_order_ids: tuple[str, ...] = ()
        safety_check = TradingSafetyCheck(
            mode=TradingMode.LIVE,
            allowed=True,
        )
        self.historical_order = LiveOrderRecord(
            client_order_id="historical-order",
            broker_order_id="historical-broker-order",
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            request=OrderRequest(
                symbol="F",
                side=OrderSide.BUY,
                quantity=1,
            ),
            reference_price=10,
            notional=10,
            safety_check=safety_check,
            status=LiveOrderStatus.FILLED,
            raw_response_ref="alpaca-paper:historical-order",
        )
        self.historical_fill = LiveFillRecord(
            order_record_id=self.historical_order.id,
            client_order_id=self.historical_order.client_order_id,
            broker_order_id=self.historical_order.broker_order_id or "",
            broker_execution_id="historical-execution",
            broker_name="alpaca-paper",
            account_id="acct-1",
            broker_environment="paper",
            symbol="F",
            side=OrderSide.BUY,
            quantity=1,
            price=10,
            raw_response_ref="alpaca-paper:historical-fill",
        )

    def remember_order_record(self, record: LiveOrderRecord) -> None:
        self.remembered_client_order_ids = (
            *self.remembered_client_order_ids,
            record.client_order_id,
        )

    def fills(self) -> tuple[LiveFillRecord, ...]:
        if self.historical_order.client_order_id not in (
            self.remembered_client_order_ids
        ):
            return ()
        return (self.historical_fill,)


class DelayedFillAlpacaPaperWorkflowClient(FakeAlpacaPaperWorkflowClient):
    def __init__(self) -> None:
        super().__init__()
        self.refresh_calls = 0
        self._pending_fill: LiveFillRecord | None = None

    def submit_market_order(
        self,
        request,
        *,
        reference_price,
        client_order_id,
        safety_check,
    ) -> LiveOrderRecord:
        record = super().submit_market_order(
            request,
            reference_price=reference_price,
            client_order_id=client_order_id,
            safety_check=safety_check,
        )
        self._pending_fill = self._fills.pop()
        self._cash = 1000.0
        self._positions = {}
        return record.model_copy(update={"status": LiveOrderStatus.ACCEPTED})

    def refresh_order_record(
        self,
        record: LiveOrderRecord,
    ) -> LiveOrderRecord:
        self.refresh_calls += 1
        if self._pending_fill is not None:
            fill = self._pending_fill
            self._pending_fill = None
            self._fills.append(fill)
            self._apply_fill(fill)
        return record.model_copy(update={"status": LiveOrderStatus.FILLED})


class CancelledAlpacaPaperWorkflowClient(DelayedFillAlpacaPaperWorkflowClient):
    def refresh_order_record(
        self,
        record: LiveOrderRecord,
    ) -> LiveOrderRecord:
        self.refresh_calls += 1
        return record.model_copy(update={"status": LiveOrderStatus.CANCELLED})


def _alpaca_paper_safety_config(
    *,
    short_selling_policy: ShortSellingPolicy | None = None,
) -> TradingSafetyConfig:
    return TradingSafetyConfig(
        mode=TradingMode.LIVE,
        live_trading_enabled=True,
        live_trading_confirmation=LIVE_TRADING_CONFIRMATION,
        max_order_notional=1000,
        broker_name="alpaca-paper",
        short_selling_policy=short_selling_policy or ShortSellingPolicy(),
    )
