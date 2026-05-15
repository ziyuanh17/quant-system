from pathlib import Path

from quant.models.operations import (
    DashboardHealthIssue,
    DashboardHealthStatus,
    HealthReport,
)


def build_dashboard_health_status(
    report: HealthReport,
) -> DashboardHealthStatus:
    """Create a public-safe health snapshot for the static dashboard."""
    # Keep this mapping explicit so newly added HealthReport fields do not
    # become public dashboard fields by accident.
    return DashboardHealthStatus(
        status=report.status,
        latest_run_status=report.latest_run_status,
        latest_run_completed_at=report.latest_run_completed_at,
        latest_signal_action=report.latest_signal_action,
        latest_signal_date=report.latest_signal_date,
        latest_signal_skipped=report.latest_signal_skipped,
        lock_status=report.lock_status,
        reconciliation_status=report.reconciliation_status,
        reconciliation_difference_count=report.reconciliation_difference_count,
        issue_count=report.issue_count,
        issues=tuple(
            DashboardHealthIssue(
                code=issue.code,
                severity=issue.severity,
                message=issue.message,
            )
            for issue in report.issues
        ),
    )


def write_dashboard_health_status(
    status: DashboardHealthStatus,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(status.model_dump_json(indent=2) + "\n")
    return path
