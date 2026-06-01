from datetime import datetime
from pathlib import Path

from pydantic import BaseModel, ValidationError

from quant.execution.reconciliation import (
    reconcile_paper_state,
    write_paper_state_reconciliation_report,
)
from quant.models.execution import (
    LiveReconciliationReport,
    LiveReconciliationStatus,
    PaperBrokerState,
    PaperDryRunComparisonReport,
    PaperDryRunComparisonStatus,
    PaperSignalRecord,
)
from quant.models.operations import (
    HealthIssue,
    HealthIssueSeverity,
    HealthReport,
    HealthStatus,
)
from quant.models.scheduler import ScheduledRunRecord, ScheduledRunStatus
from quant.models.workflow import DataRefreshWorkflowRecord, WorkflowRunStatus
from quant.operations.locks import read_lock_record


def build_health_report(
    *,
    run_records_dir: Path,
    signal_records_dir: Path,
    state_path: Path,
    logs_dir: Path,
    lock_path: Path | None = None,
    lock_stale_after_seconds: int = 7200,
    reconcile_state: bool = False,
    initial_cash: float = 100_000,
    cash_tolerance: float = 0.01,
    reconciliation_report_path: Path | None = None,
    check_comparison: bool = False,
    comparison_report_path: Path | None = None,
    check_alpaca_paper: bool = False,
    alpaca_paper_workflow_records_dir: Path | None = None,
    alpaca_paper_reconciliation_report_path: Path | None = None,
) -> HealthReport:
    """Inspect local service artifacts without mutating account or run state."""
    issues: list[HealthIssue] = []

    # The latest scheduler record tells us whether the recurring job itself is
    # completing. A failed latest run is a hard operational failure.
    latest_run_path = _latest_json(run_records_dir)
    latest_run_status: str | None = None
    latest_run_completed_at = None
    if latest_run_path is None:
        issues.append(
            _warning(
                "missing_scheduler_run",
                f"No scheduler run records found in {run_records_dir}.",
            )
        )
    else:
        run_record = _parse_model(
            ScheduledRunRecord,
            latest_run_path,
            issues,
            code="invalid_scheduler_run",
        )
        if run_record is not None:
            latest_run_status = run_record.status.value
            latest_run_completed_at = run_record.completed_at
            if run_record.status == ScheduledRunStatus.FAILED:
                issues.append(
                    _error(
                        "latest_scheduler_run_failed",
                        f"Latest scheduler run failed: {run_record.message}",
                    )
                )

    latest_signal_path = _latest_json(signal_records_dir)
    latest_signal_action: str | None = None
    latest_signal_date: str | None = None
    latest_signal_skipped: bool | None = None
    # Signal records are the audit trail between strategy output and broker
    # intent. Missing records are a warning because a brand-new service may not
    # have emitted its first signal yet.
    if latest_signal_path is None:
        issues.append(
            _warning(
                "missing_paper_signal",
                f"No paper signal records found in {signal_records_dir}.",
            )
        )
    else:
        signal_record = _parse_model(
            PaperSignalRecord,
            latest_signal_path,
            issues,
            code="invalid_paper_signal",
        )
        if signal_record is not None:
            latest_signal_action = signal_record.decision.action.value
            latest_signal_date = signal_record.decision.signal_date
            latest_signal_skipped = signal_record.skipped

    state: PaperBrokerState | None = None
    state_cash: float | None = None
    state_position_count: int | None = None
    # Paper state is critical: without it, scheduled invocations cannot behave
    # like one continuous account, so missing or invalid state is failed health.
    if not state_path.exists():
        issues.append(
            _error(
                "missing_paper_state",
                f"Paper broker state file does not exist: {state_path}.",
            )
        )
    else:
        state = _parse_model(
            PaperBrokerState,
            state_path,
            issues,
            code="invalid_paper_state",
        )
        if state is not None:
            state_cash = state.cash
            state_position_count = len(state.positions)

    log_count = _count_logs(logs_dir)
    # Logs are useful for human debugging, but missing logs alone should not
    # make a paper account look broken while the artifact records are healthy.
    if not logs_dir.exists():
        issues.append(
            _warning(
                "missing_logs_dir",
                f"Logs directory does not exist: {logs_dir}.",
            )
        )
    elif log_count == 0:
        issues.append(
            _warning("missing_logs", f"No log files found in {logs_dir}.")
        )

    lock_status = "not_checked"
    lock_owner: str | None = None
    lock_expires_at = None
    if lock_path is not None:
        lock_status, lock_owner, lock_expires_at = _check_lock(
            lock_path=lock_path,
            lock_stale_after_seconds=lock_stale_after_seconds,
            issues=issues,
        )

    reconciliation_status = "skipped"
    reconciliation_difference_count: int | None = None
    if reconcile_state:
        reconciliation_status = "unavailable"
        if state is not None:
            try:
                report = reconcile_paper_state(
                    state=state,
                    state_path=state_path,
                    signal_records_dir=signal_records_dir,
                    initial_cash=initial_cash,
                    cash_tolerance=cash_tolerance,
                )
                reconciliation_difference_count = report.difference_count
                reconciliation_status = "passed" if report.passed else "failed"
                if reconciliation_report_path is not None:
                    write_paper_state_reconciliation_report(
                        report,
                        reconciliation_report_path,
                    )
                if not report.passed:
                    issues.append(
                        _error(
                            "paper_state_reconciliation_failed",
                            "Paper state does not match signal audit records.",
                        )
                    )
            except Exception as exc:
                issues.append(
                    _error(
                        "paper_state_reconciliation_error",
                        f"Could not reconcile paper state: {exc}",
                    )
                )

    comparison_status = "skipped"
    comparison_difference_count: int | None = None
    if check_comparison:
        comparison_status = "unavailable"
        if comparison_report_path is None:
            issues.append(
                _warning(
                    "missing_comparison_report_path",
                    "Comparison check requested without a report path.",
                )
            )
        elif not comparison_report_path.exists():
            issues.append(
                _warning(
                    "missing_comparison_report",
                    "Comparison report does not exist: "
                    f"{comparison_report_path}.",
                )
            )
        else:
            comparison_report = _parse_model(
                PaperDryRunComparisonReport,
                comparison_report_path,
                issues,
                code="invalid_comparison_report",
            )
            if comparison_report is not None:
                comparison_difference_count = (
                    comparison_report.difference_count
                )
                comparison_status = comparison_report.status.value
                if (
                    comparison_report.status
                    == PaperDryRunComparisonStatus.FAILED
                ):
                    issues.append(
                        _error(
                            "paper_dry_run_comparison_failed",
                            "Paper signal and dry-run order diverged.",
                        )
                    )

    alpaca_paper_workflow_path: Path | None = None
    alpaca_paper_workflow_status = "skipped"
    alpaca_paper_latest_signal_action: str | None = None
    alpaca_paper_latest_signal_reason: str | None = None
    alpaca_paper_latest_signal_market_price: float | None = None
    alpaca_paper_broker_submission_attempted: bool | None = None
    alpaca_paper_broker_submission_skipped_reason: str | None = None
    alpaca_paper_order_artifact_count: int | None = None
    alpaca_paper_fill_artifact_count: int | None = None
    alpaca_paper_snapshot_artifact_count: int | None = None
    alpaca_paper_reconciliation_status = "skipped"
    alpaca_paper_reconciliation_difference_count: int | None = None
    if check_alpaca_paper:
        alpaca_paper_workflow_status = "unavailable"
        alpaca_paper_reconciliation_status = "unavailable"

        if alpaca_paper_workflow_records_dir is None:
            issues.append(
                _warning(
                    "missing_alpaca_paper_workflow_records_dir",
                    "Alpaca paper check requested without a workflow "
                    "records directory.",
                )
            )
        else:
            alpaca_paper_workflow_path = _latest_json(
                alpaca_paper_workflow_records_dir
            )
            if alpaca_paper_workflow_path is None:
                issues.append(
                    _warning(
                        "missing_alpaca_paper_workflow_record",
                        "No Alpaca paper workflow records found in "
                        f"{alpaca_paper_workflow_records_dir}.",
                    )
                )
            else:
                workflow_record = _parse_model(
                    DataRefreshWorkflowRecord,
                    alpaca_paper_workflow_path,
                    issues,
                    code="invalid_alpaca_paper_workflow_record",
                )
                if workflow_record is not None:
                    alpaca_paper_workflow_status = (
                        workflow_record.status.value
                    )
                    alpaca_paper_latest_signal_action = (
                        workflow_record.latest_signal_action
                    )
                    alpaca_paper_latest_signal_reason = (
                        workflow_record.latest_signal_reason
                    )
                    alpaca_paper_latest_signal_market_price = (
                        workflow_record.latest_signal_market_price
                    )
                    alpaca_paper_broker_submission_attempted = (
                        workflow_record.broker_submission_attempted
                    )
                    alpaca_paper_broker_submission_skipped_reason = (
                        workflow_record.broker_submission_skipped_reason
                    )
                    alpaca_paper_order_artifact_count = len(
                        workflow_record.order_artifact_paths
                    )
                    alpaca_paper_fill_artifact_count = len(
                        workflow_record.fill_artifact_paths
                    )
                    alpaca_paper_snapshot_artifact_count = len(
                        workflow_record.snapshot_artifact_paths
                    )
                    if workflow_record.status == WorkflowRunStatus.FAILED:
                        issues.append(
                            _error(
                                "alpaca_paper_workflow_failed",
                                "Latest Alpaca paper workflow failed: "
                                f"{workflow_record.message}",
                            )
                        )

        if alpaca_paper_reconciliation_report_path is None:
            issues.append(
                _warning(
                    "missing_alpaca_paper_reconciliation_report_path",
                    "Alpaca paper check requested without a reconciliation "
                    "report path.",
                )
            )
        elif not alpaca_paper_reconciliation_report_path.exists():
            issues.append(
                _warning(
                    "missing_alpaca_paper_reconciliation_report",
                    "Alpaca paper reconciliation report does not exist: "
                    f"{alpaca_paper_reconciliation_report_path}.",
                )
            )
        else:
            live_report = _parse_model(
                LiveReconciliationReport,
                alpaca_paper_reconciliation_report_path,
                issues,
                code="invalid_alpaca_paper_reconciliation_report",
            )
            if live_report is not None:
                alpaca_paper_reconciliation_status = (
                    live_report.status.value
                )
                alpaca_paper_reconciliation_difference_count = (
                    live_report.difference_count
                )
                if live_report.status == LiveReconciliationStatus.FAILED:
                    issues.append(
                        _error(
                            "alpaca_paper_reconciliation_failed",
                            "Alpaca paper local artifacts diverged from "
                            "broker state.",
                        )
                    )

    return HealthReport(
        status=_status_from_issues(issues),
        run_records_dir=str(run_records_dir),
        signal_records_dir=str(signal_records_dir),
        state_path=str(state_path),
        logs_dir=str(logs_dir),
        latest_run_path=str(latest_run_path) if latest_run_path else None,
        latest_run_status=latest_run_status,
        latest_run_completed_at=latest_run_completed_at,
        latest_signal_path=(
            str(latest_signal_path) if latest_signal_path else None
        ),
        latest_signal_action=latest_signal_action,
        latest_signal_date=latest_signal_date,
        latest_signal_skipped=latest_signal_skipped,
        state_cash=state_cash,
        state_position_count=state_position_count,
        log_count=log_count,
        lock_path=str(lock_path) if lock_path is not None else None,
        lock_status=lock_status,
        lock_owner=lock_owner,
        lock_expires_at=lock_expires_at,
        reconciliation_status=reconciliation_status,
        reconciliation_difference_count=reconciliation_difference_count,
        reconciliation_report_path=(
            str(reconciliation_report_path)
            if reconciliation_report_path is not None
            else None
        ),
        comparison_status=comparison_status,
        comparison_difference_count=comparison_difference_count,
        comparison_report_path=(
            str(comparison_report_path)
            if comparison_report_path is not None
            else None
        ),
        alpaca_paper_workflow_records_dir=(
            str(alpaca_paper_workflow_records_dir)
            if alpaca_paper_workflow_records_dir is not None
            else None
        ),
        alpaca_paper_workflow_path=(
            str(alpaca_paper_workflow_path)
            if alpaca_paper_workflow_path is not None
            else None
        ),
        alpaca_paper_workflow_status=alpaca_paper_workflow_status,
        alpaca_paper_latest_signal_action=(
            alpaca_paper_latest_signal_action
        ),
        alpaca_paper_latest_signal_reason=(
            alpaca_paper_latest_signal_reason
        ),
        alpaca_paper_latest_signal_market_price=(
            alpaca_paper_latest_signal_market_price
        ),
        alpaca_paper_broker_submission_attempted=(
            alpaca_paper_broker_submission_attempted
        ),
        alpaca_paper_broker_submission_skipped_reason=(
            alpaca_paper_broker_submission_skipped_reason
        ),
        alpaca_paper_order_artifact_count=(
            alpaca_paper_order_artifact_count
        ),
        alpaca_paper_fill_artifact_count=alpaca_paper_fill_artifact_count,
        alpaca_paper_snapshot_artifact_count=(
            alpaca_paper_snapshot_artifact_count
        ),
        alpaca_paper_reconciliation_status=(
            alpaca_paper_reconciliation_status
        ),
        alpaca_paper_reconciliation_difference_count=(
            alpaca_paper_reconciliation_difference_count
        ),
        alpaca_paper_reconciliation_report_path=(
            str(alpaca_paper_reconciliation_report_path)
            if alpaca_paper_reconciliation_report_path is not None
            else None
        ),
        issues=tuple(issues),
    )


def _check_lock(
    *,
    lock_path: Path,
    lock_stale_after_seconds: int,
    issues: list[HealthIssue],
) -> tuple[str, str | None, datetime | None]:
    if lock_stale_after_seconds <= 0:
        issues.append(
            _error(
                "invalid_lock_stale_after_seconds",
                "lock-stale-after-seconds must be positive.",
            )
        )
        return "invalid", None, None
    if not lock_path.exists():
        return "missing", None, None

    record = read_lock_record(lock_path)
    if record is None:
        issues.append(
            _error("invalid_lock", f"Could not read lock file: {lock_path}.")
        )
        return "invalid", None, None
    if record.is_stale():
        issues.append(
            _error(
                "stale_lock",
                f"Workflow lock is stale: {lock_path}.",
            )
        )
        return "stale", record.owner, record.expires_at

    issues.append(
        _warning(
            "active_lock",
            f"Workflow lock is active: {lock_path}.",
        )
    )
    return "active", record.owner, record.expires_at


def _latest_json(directory: Path) -> Path | None:
    if not directory.exists():
        return None
    files = [path for path in directory.glob("*.json") if path.is_file()]
    if not files:
        return None
    return max(files, key=lambda path: path.stat().st_mtime)


def _parse_model[ModelT: BaseModel](
    model_type: type[ModelT],
    path: Path,
    issues: list[HealthIssue],
    *,
    code: str,
) -> ModelT | None:
    try:
        return model_type.model_validate_json(path.read_text())
    except (OSError, ValidationError, ValueError) as exc:
        issues.append(_error(code, f"Could not read {path}: {exc}"))
        return None


def _count_logs(logs_dir: Path) -> int:
    if not logs_dir.exists():
        return 0
    return sum(1 for path in logs_dir.iterdir() if path.is_file())


def _status_from_issues(issues: list[HealthIssue]) -> HealthStatus:
    if any(issue.severity == HealthIssueSeverity.ERROR for issue in issues):
        return HealthStatus.FAILED
    if issues:
        return HealthStatus.DEGRADED
    return HealthStatus.HEALTHY


def _warning(code: str, message: str) -> HealthIssue:
    return HealthIssue(
        code=code,
        severity=HealthIssueSeverity.WARNING,
        message=message,
    )


def _error(code: str, message: str) -> HealthIssue:
    return HealthIssue(
        code=code,
        severity=HealthIssueSeverity.ERROR,
        message=message,
    )
