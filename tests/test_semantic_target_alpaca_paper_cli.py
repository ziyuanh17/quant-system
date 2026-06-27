"""Test semantic-target Alpaca paper fake-rehearsal CLI."""

from pathlib import Path

from typer.testing import CliRunner

from quant.cli import app
from quant.models.operator import SemanticTargetAlpacaPaperRehearsalReport


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


def _report_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        if line.startswith("Report: "):
            return Path(line.removeprefix("Report: "))
    raise AssertionError(f"report path missing from output: {output}")
