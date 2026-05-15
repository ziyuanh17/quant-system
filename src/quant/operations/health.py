from pathlib import Path

from pydantic import BaseModel, ValidationError

from quant.models.execution import PaperBrokerState, PaperSignalRecord
from quant.models.operations import (
    HealthIssue,
    HealthIssueSeverity,
    HealthReport,
    HealthStatus,
)
from quant.models.scheduler import ScheduledRunRecord, ScheduledRunStatus


def build_health_report(
    *,
    run_records_dir: Path,
    signal_records_dir: Path,
    state_path: Path,
    logs_dir: Path,
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
        issues=tuple(issues),
    )


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
