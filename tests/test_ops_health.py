import json
from datetime import UTC, datetime, timedelta

from typer.testing import CliRunner

from quant.cli import app
from quant.execution import PaperBroker, save_paper_broker_state
from quant.execution.artifacts import write_paper_signal_record
from quant.models.execution import (
    LiveReconciliationDifference,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderRequest,
    OrderSide,
    PaperBrokerState,
    PaperDryRunComparisonReport,
    PaperDryRunComparisonStatus,
    PaperDryRunDifference,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
    PortfolioSnapshot,
)
from quant.models.operations import HealthStatus, RunLockRecord
from quant.models.scheduler import ScheduledRunRecord, ScheduledRunStatus
from quant.models.workflow import DataRefreshWorkflowRecord, WorkflowRunStatus
from quant.operations import FileLock, build_health_report


def test_health_report_is_healthy_when_service_artifacts_are_readable(
    tmp_path,
) -> None:
    paths = _write_health_artifacts(tmp_path)

    report = build_health_report(**paths)

    assert report.status == HealthStatus.HEALTHY
    assert report.issue_count == 0
    assert report.latest_run_status == "succeeded"
    assert report.latest_signal_action == "buy"
    assert report.state_cash == 1000
    assert report.log_count == 1


def test_health_report_fails_when_paper_state_is_missing(tmp_path) -> None:
    paths = _write_health_artifacts(tmp_path)
    paths["state_path"].unlink()

    report = build_health_report(**paths)

    assert report.status == HealthStatus.FAILED
    assert [issue.code for issue in report.issues] == ["missing_paper_state"]


def test_health_report_fails_when_latest_scheduler_run_failed(
    tmp_path,
) -> None:
    paths = _write_health_artifacts(
        tmp_path,
        run_status=ScheduledRunStatus.FAILED,
    )

    report = build_health_report(**paths)

    assert report.status == HealthStatus.FAILED
    assert "latest_scheduler_run_failed" in {
        issue.code for issue in report.issues
    }


def test_ops_health_cli_prints_healthy_report(tmp_path) -> None:
    paths = _write_health_artifacts(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "health",
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
        ],
    )

    assert result.exit_code == 0
    assert "Status: healthy" in result.output
    assert "Latest run: succeeded" in result.output
    assert "Latest signal: action=buy" in result.output
    assert "Issues: 0" in result.output
    assert "Lock: status=missing" in result.output
    assert "Reconciliation: status=skipped" in result.output


def test_ops_health_cli_exits_nonzero_for_failed_health(tmp_path) -> None:
    paths = _write_health_artifacts(tmp_path)
    paths["state_path"].unlink()

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "health",
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
        ],
    )

    assert result.exit_code == 1
    assert "Status: failed" in result.output
    assert "[error] missing_paper_state" in result.output


def test_health_report_is_degraded_when_lock_is_active(tmp_path) -> None:
    paths = _write_health_artifacts(tmp_path)
    lock_path = tmp_path / "locks" / "workflow.lock"
    lock = FileLock(
        path=lock_path,
        lock_name="paper-signal-refresh",
        owner="active-run",
        stale_after_seconds=60,
    )
    lock.acquire()

    try:
        report = build_health_report(**paths, lock_path=lock_path)
    finally:
        lock.release()

    assert report.status == HealthStatus.DEGRADED
    assert report.lock_status == "active"
    assert report.lock_owner == "active-run"
    assert "active_lock" in {issue.code for issue in report.issues}


def test_health_report_fails_when_lock_is_stale(tmp_path) -> None:
    paths = _write_health_artifacts(tmp_path)
    lock_path = tmp_path / "locks" / "workflow.lock"
    lock_path.parent.mkdir(parents=True)
    lock_path.write_text(
        RunLockRecord(
            lock_name="paper-signal-refresh",
            owner="old-run",
            hostname="host",
            pid=123,
            acquired_at=datetime.now(UTC) - timedelta(seconds=120),
            stale_after_seconds=60,
        ).model_dump_json()
    )

    report = build_health_report(**paths, lock_path=lock_path)

    assert report.status == HealthStatus.FAILED
    assert report.lock_status == "stale"
    assert "stale_lock" in {issue.code for issue in report.issues}


def test_health_report_reconciles_paper_state_when_requested(
    tmp_path,
) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    report_path = tmp_path / "reports" / "health-state.json"

    report = build_health_report(
        **paths,
        reconcile_state=True,
        initial_cash=1_000,
        reconciliation_report_path=report_path,
    )

    assert report.status == HealthStatus.HEALTHY
    assert report.reconciliation_status == "passed"
    assert report.reconciliation_difference_count == 0
    assert report_path.exists()


def test_health_report_fails_when_reconciliation_detects_drift(
    tmp_path,
) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    drifted_state = PaperBrokerState(cash=999)
    paths["state_path"].write_text(drifted_state.model_dump_json())

    report = build_health_report(
        **paths,
        reconcile_state=True,
        initial_cash=1_000,
    )

    assert report.status == HealthStatus.FAILED
    assert report.reconciliation_status == "failed"
    assert report.reconciliation_difference_count is not None
    assert report.reconciliation_difference_count > 0
    assert "paper_state_reconciliation_failed" in {
        issue.code for issue in report.issues
    }


def test_ops_health_cli_can_reconcile_state(tmp_path) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    report_path = tmp_path / "reports" / "health-state.json"

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "health",
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
            "--reconcile-state",
            "--initial-cash",
            "1000",
            "--reconciliation-report-path",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "Reconciliation: status=passed differences=0" in result.output
    assert report_path.exists()


def test_health_report_fails_when_comparison_report_failed(tmp_path) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    comparison_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    _write_comparison_report(comparison_path, passed=False)

    report = build_health_report(
        **paths,
        check_comparison=True,
        comparison_report_path=comparison_path,
    )

    assert report.status == HealthStatus.FAILED
    assert report.comparison_status == "failed"
    assert report.comparison_difference_count == 1
    assert "paper_dry_run_comparison_failed" in {
        issue.code for issue in report.issues
    }


def test_ops_health_cli_can_check_comparison_report(tmp_path) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    comparison_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    _write_comparison_report(comparison_path, passed=True)

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "health",
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
            "--check-comparison",
            "--comparison-report-path",
            str(comparison_path),
        ],
    )

    assert result.exit_code == 0
    assert "Comparison: status=passed differences=0" in result.output


def test_health_report_checks_alpaca_paper_workflow_and_reconciliation(
    tmp_path,
) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    workflow_records_dir = tmp_path / "workflows" / "alpaca-paper-refresh"
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"
    _write_alpaca_paper_workflow_record(workflow_records_dir, passed=True)
    _write_live_reconciliation_report(reconciliation_path, passed=True)

    report = build_health_report(
        **paths,
        check_alpaca_paper=True,
        alpaca_paper_workflow_records_dir=workflow_records_dir,
        alpaca_paper_reconciliation_report_path=reconciliation_path,
    )

    assert report.status == HealthStatus.HEALTHY
    assert report.alpaca_paper_workflow_status == "succeeded"
    assert report.alpaca_paper_reconciliation_status == "passed"
    assert report.alpaca_paper_reconciliation_difference_count == 0


def test_health_report_fails_when_alpaca_paper_reconciliation_failed(
    tmp_path,
) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    workflow_records_dir = tmp_path / "workflows" / "alpaca-paper-refresh"
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"
    _write_alpaca_paper_workflow_record(workflow_records_dir, passed=True)
    _write_live_reconciliation_report(reconciliation_path, passed=False)

    report = build_health_report(
        **paths,
        check_alpaca_paper=True,
        alpaca_paper_workflow_records_dir=workflow_records_dir,
        alpaca_paper_reconciliation_report_path=reconciliation_path,
    )

    assert report.status == HealthStatus.FAILED
    assert report.alpaca_paper_reconciliation_status == "failed"
    assert report.alpaca_paper_reconciliation_difference_count == 1
    assert "alpaca_paper_reconciliation_failed" in {
        issue.code for issue in report.issues
    }


def test_ops_health_cli_can_check_alpaca_paper_health(tmp_path) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    workflow_records_dir = tmp_path / "workflows" / "alpaca-paper-refresh"
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"
    _write_alpaca_paper_workflow_record(workflow_records_dir, passed=True)
    _write_live_reconciliation_report(reconciliation_path, passed=True)

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "health",
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
            "--check-alpaca-paper",
            "--alpaca-paper-workflow-records-dir",
            str(workflow_records_dir),
            "--alpaca-paper-reconciliation-report-path",
            str(reconciliation_path),
        ],
    )

    assert result.exit_code == 0
    assert "Alpaca paper: workflow=succeeded reconciliation=passed" in (
        result.output
    )


def test_ops_publish_status_writes_sanitized_dashboard_json(tmp_path) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    output_path = tmp_path / "site" / "status.json"
    comparison_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    _write_comparison_report(comparison_path, passed=True)

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "publish-status",
            "--output-path",
            str(output_path),
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
            "--initial-cash",
            "1000",
            "--comparison-report-path",
            str(comparison_path),
        ],
    )

    payload = json.loads(output_path.read_text())
    assert result.exit_code == 0
    assert "Status: healthy" in result.output
    assert payload["status"] == "healthy"
    assert payload["reconciliation_status"] == "passed"
    assert payload["reconciliation_difference_count"] == 0
    assert payload["comparison_status"] == "passed"
    assert payload["comparison_difference_count"] == 0
    assert "state_cash" not in payload
    assert "state_position_count" not in payload


def test_ops_publish_status_can_include_sanitized_alpaca_paper_health(
    tmp_path,
) -> None:
    paths = _write_reconciled_health_artifacts(tmp_path)
    output_path = tmp_path / "site" / "status.json"
    workflow_records_dir = tmp_path / "workflows" / "alpaca-paper-refresh"
    reconciliation_path = tmp_path / "live" / "reconciliation" / "latest.json"
    _write_alpaca_paper_workflow_record(workflow_records_dir, passed=True)
    _write_live_reconciliation_report(reconciliation_path, passed=True)

    result = CliRunner().invoke(
        app,
        [
            "ops",
            "publish-status",
            "--output-path",
            str(output_path),
            "--run-records-dir",
            str(paths["run_records_dir"]),
            "--signal-records-dir",
            str(paths["signal_records_dir"]),
            "--state-path",
            str(paths["state_path"]),
            "--logs-dir",
            str(paths["logs_dir"]),
            "--initial-cash",
            "1000",
            "--check-alpaca-paper",
            "--alpaca-paper-workflow-records-dir",
            str(workflow_records_dir),
            "--alpaca-paper-reconciliation-report-path",
            str(reconciliation_path),
        ],
    )

    payload = json.loads(output_path.read_text())
    assert result.exit_code == 0
    assert payload["alpaca_paper_workflow_status"] == "succeeded"
    assert payload["alpaca_paper_reconciliation_status"] == "passed"
    assert payload["alpaca_paper_reconciliation_difference_count"] == 0
    assert payload["alpaca_paper_latest_signal_action"] == "hold"
    assert payload["alpaca_paper_latest_signal_reason"] == (
        "latest strategy signal is hold"
    )
    assert payload["alpaca_paper_latest_signal_market_price"] == 10.0
    assert payload["alpaca_paper_broker_submission_attempted"] is False
    assert payload["alpaca_paper_broker_submission_skipped_reason"] == (
        "latest strategy signal is hold"
    )
    assert payload["alpaca_paper_order_artifact_count"] == 0
    assert payload["alpaca_paper_fill_artifact_count"] == 0
    assert payload["alpaca_paper_snapshot_artifact_count"] == 1
    assert "account_id" not in payload
    assert "state_cash" not in payload


def _write_health_artifacts(
    tmp_path,
    *,
    run_status: ScheduledRunStatus = ScheduledRunStatus.SUCCEEDED,
):
    run_records_dir = tmp_path / "runs"
    signal_records_dir = tmp_path / "signals"
    logs_dir = tmp_path / "logs"
    state_path = tmp_path / "state" / "paper.json"

    for directory in (
        run_records_dir,
        signal_records_dir,
        logs_dir,
        state_path.parent,
    ):
        directory.mkdir(parents=True, exist_ok=True)

    started_at = datetime(2024, 1, 25, 10, tzinfo=UTC)
    (run_records_dir / "run-1.json").write_text(
        ScheduledRunRecord(
            run_id="run-1",
            task_name="paper-signal",
            status=run_status,
            started_at=started_at,
            completed_at=datetime(2024, 1, 25, 10, 1, tzinfo=UTC),
            message=(
                "done"
                if run_status == ScheduledRunStatus.SUCCEEDED
                else "boom"
            ),
        ).model_dump_json()
    )

    (signal_records_dir / "signal-1.json").write_text(
        PaperSignalRecord(
            decision=PaperSignalDecision(
                symbol="AAPL",
                action=PaperSignalAction.BUY,
                signal_date="2024-01-25",
                market_price=20,
                reason="entry signal",
                idempotency_key="momentum:AAPL:2024-01-25:buy",
            ),
            trade=None,
            snapshot=PortfolioSnapshot(cash=1000, positions=()),
        ).model_dump_json()
    )
    state_path.write_text(PaperBrokerState(cash=1000).model_dump_json())
    (logs_dir / "paper-signal.log").write_text("ok\n")

    return {
        "run_records_dir": run_records_dir,
        "signal_records_dir": signal_records_dir,
        "state_path": state_path,
        "logs_dir": logs_dir,
    }


def _write_reconciled_health_artifacts(tmp_path):
    paths = _write_health_artifacts(tmp_path)
    broker = PaperBroker(initial_cash=1_000)
    trade = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        market_price=10,
    )
    key = "momentum:AAPL:2024-01-25:buy"
    broker.mark_signal_processed(key)
    signal_record = PaperSignalRecord(
        decision=PaperSignalDecision(
            symbol="AAPL",
            action=PaperSignalAction.BUY,
            signal_date="2024-01-25",
            market_price=10,
            reason="entry signal",
            idempotency_key=key,
        ),
        trade=trade,
        snapshot=trade.snapshot,
    )
    for path in paths["signal_records_dir"].glob("*.json"):
        path.unlink()
    write_paper_signal_record(signal_record, paths["signal_records_dir"])
    save_paper_broker_state(broker.state(), paths["state_path"])
    return paths


def _write_comparison_report(path, *, passed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    differences = ()
    if not passed:
        differences = (
            PaperDryRunDifference(
                field="quantity",
                paper_value="2",
                dry_run_value="1",
                message="paper fill quantity and dry-run quantity do not match",
            ),
        )
    report = PaperDryRunComparisonReport(
        paper_signal_path="paper.json",
        dry_run_order_path="dry-run.json",
        status=(
            PaperDryRunComparisonStatus.PASSED
            if passed
            else PaperDryRunComparisonStatus.FAILED
        ),
        paper_action=PaperSignalAction.BUY,
        dry_run_side=OrderSide.BUY,
        paper_symbol="AAPL",
        dry_run_symbol="AAPL",
        paper_quantity=2,
        dry_run_quantity=2 if passed else 1,
        paper_market_price=10,
        dry_run_market_price=10,
        paper_signal_date="2024-01-25",
        difference_tolerance=0.01,
        difference_count=len(differences),
        differences=differences,
    )
    path.write_text(report.model_dump_json(indent=2) + "\n")


def _write_alpaca_paper_workflow_record(path, *, passed: bool) -> None:
    path.mkdir(parents=True, exist_ok=True)
    record = DataRefreshWorkflowRecord(
        workflow_name="alpaca-paper-refresh",
        status=(
            WorkflowRunStatus.SUCCEEDED
            if passed
            else WorkflowRunStatus.FAILED
        ),
        started_at=datetime(2024, 1, 25, 10, tzinfo=UTC),
        provider="fake",
        symbol="AAPL",
        request_start="2024-01-01",
        message="ok" if passed else "boom",
        latest_signal_action="hold",
        latest_signal_reason="latest strategy signal is hold",
        latest_signal_market_price=10.0,
        broker_submission_attempted=False,
        broker_submission_skipped_reason="latest strategy signal is hold",
        snapshot_artifact_paths=("data/live/account_snapshots/snapshot.json",),
        reconciliation_report_path="data/live/reconciliation/latest.json",
    )
    (path / f"{record.workflow_id}.json").write_text(
        record.model_dump_json(indent=2) + "\n"
    )


def _write_live_reconciliation_report(path, *, passed: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    differences = ()
    if not passed:
        differences = (
            LiveReconciliationDifference(
                field="fills.count",
                local_value="1",
                broker_value="0",
                message="local and broker fill counts differ",
            ),
        )
    report = LiveReconciliationReport(
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        local_order_count=1,
        broker_order_count=1,
        local_fill_count=1,
        broker_fill_count=1 if passed else 0,
        local_position_count=1,
        broker_position_count=1,
        status=(
            LiveReconciliationStatus.PASSED
            if passed
            else LiveReconciliationStatus.FAILED
        ),
        differences=differences,
    )
    path.write_text(report.model_dump_json(indent=2) + "\n")
