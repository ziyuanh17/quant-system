from datetime import UTC, datetime

from typer.testing import CliRunner

from quant.cli import app
from quant.models.execution import (
    PaperBrokerState,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
    PortfolioSnapshot,
)
from quant.models.operations import HealthStatus
from quant.models.scheduler import ScheduledRunRecord, ScheduledRunStatus
from quant.operations import build_health_report


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
