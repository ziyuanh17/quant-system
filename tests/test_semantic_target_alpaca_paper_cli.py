"""Test semantic-target Alpaca paper fake-rehearsal CLI."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

from typer.testing import CliRunner

import quant.cli
from quant.cli import app
from quant.execution import FakeLiveBrokerClient
from quant.models.operator import (
    SemanticTargetAlpacaPaperOperatorRequest,
    SemanticTargetAlpacaPaperRehearsalReport,
)
from quant.workflows import run_semantic_target_alpaca_paper_fake_rehearsal


def test_alpaca_paper_fake_rehearsal_cli_writes_verified_report(
    tmp_path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "alpaca-paper-fake-rehearsal",
            "--rehearsal-id",
            "cli-alpaca-paper-fake",
            "--output-root",
            str(tmp_path / "rehearsal"),
        ],
    )

    assert result.exit_code == 0
    assert "Passed: yes" in result.output
    assert "First status: satisfied" in result.output
    assert "Second status: satisfied" in result.output
    assert "Orders: 1" in result.output
    assert "Fills: 1" in result.output
    report_path = _report_path_from_output(result.output)
    report = SemanticTargetAlpacaPaperRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    assert report.passed
    assert report.prohibited_api_calls == ()


def test_alpaca_paper_fake_rehearsal_help_is_fake_client_only() -> None:
    result = CliRunner().invoke(
        app,
        ["semantic-target", "alpaca-paper-fake-rehearsal", "--help"],
    )

    assert result.exit_code == 0
    assert "fake-client" in result.output.lower()
    assert "scheduler" not in result.output.lower()
    assert "launchd" not in result.output.lower()
    assert "credential" not in result.output.lower()


def test_alpaca_paper_cli_runs_reviewed_request_with_injected_paper_client(
    tmp_path,
    monkeypatch,
) -> None:
    request_path = _reviewed_request_path(tmp_path)
    client = FakeLiveBrokerClient(
        initial_cash=1_000,
        broker_name="alpaca-paper",
        account_id="acct-fake",
        broker_environment="paper",
    )

    monkeypatch.setenv("QUANT_ALPACA_PAPER_API_KEY", "paper-key")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", "acct-fake")
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        lambda config: client,
    )
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: True
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "alpaca-paper",
            "--request-path",
            str(request_path),
            "--from-env",
        ],
    )

    assert result.exit_code == 0
    assert "Status: satisfied" in result.output
    assert "Order: buy 2 AAPL" in result.output
    assert "Reconciliation: passed" in result.output
    assert (
        len(tuple((tmp_path / "operator-output" / "orders").rglob("*.json")))
        == 1
    )
    assert len(client.fills()) == 1


def test_alpaca_paper_cli_blocks_when_regular_session_closed(
    tmp_path, monkeypatch
) -> None:
    closed_session = datetime(2026, 6, 27, 16, tzinfo=UTC)
    request_path = _reviewed_request_path(tmp_path, now=closed_session)
    monkeypatch.setattr(quant.cli, "_current_utc", lambda: closed_session)
    monkeypatch.setattr(
        quant.cli, "_is_regular_us_equity_session", lambda moment: False
    )

    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "alpaca-paper",
            "--request-path",
            str(request_path),
            "--from-env",
        ],
    )

    assert result.exit_code != 0
    assert "regular US equity session is closed" in result.output


def test_regular_us_equity_session_helper_handles_open_and_closed_times():
    assert quant.cli._is_regular_us_equity_session(
        datetime(2026, 6, 29, 15, tzinfo=UTC)
    )
    assert not quant.cli._is_regular_us_equity_session(
        datetime(2026, 6, 27, 16, tzinfo=UTC)
    )
    assert not quant.cli._is_regular_us_equity_session(
        datetime(2026, 12, 25, 15, tzinfo=UTC)
    )


def test_alpaca_paper_cli_requires_from_env(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "semantic-target",
            "alpaca-paper",
            "--request-path",
            str(tmp_path / "missing.json"),
        ],
    )

    assert result.exit_code != 0
    assert "--from-env is required" in result.output


def _reviewed_request_path(
    tmp_path: Path, *, now: datetime | None = None
) -> Path:
    current = now or datetime.now(UTC)
    run_semantic_target_alpaca_paper_fake_rehearsal(
        rehearsal_id="cli-real-surface",
        output_root=tmp_path / "source",
        evaluated_at=current,
    )
    original_path = (
        tmp_path / "source" / "requests" / "cli-real-surface-request.json"
    )
    request = SemanticTargetAlpacaPaperOperatorRequest.model_validate_json(
        original_path.read_text()
    ).model_copy(
        update={
            "request_id": "cli-real-surface-live-request",
            "output_root": str(tmp_path / "operator-output"),
            "valid_until": current + timedelta(hours=1),
        }
    )
    request_path = tmp_path / "reviewed-request.json"
    request_path.write_text(request.model_dump_json(indent=2))
    return request_path


def _report_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        if line.startswith("Report: "):
            return Path(line.removeprefix("Report: "))
    raise AssertionError(f"report path missing from output: {output}")
