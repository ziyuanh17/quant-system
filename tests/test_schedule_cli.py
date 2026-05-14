import json

from typer.testing import CliRunner

from quant.cli import app


def test_schedule_paper_order_writes_run_and_paper_records(tmp_path) -> None:
    run_output_dir = tmp_path / "scheduler"
    paper_output_dir = tmp_path / "paper"

    result = CliRunner().invoke(
        app,
        [
            "schedule",
            "paper-order",
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "10",
            "--initial-cash",
            "100",
            "--iterations",
            "2",
            "--interval-seconds",
            "0",
            "--run-output-dir",
            str(run_output_dir),
            "--paper-output-dir",
            str(paper_output_dir),
        ],
    )

    run_records = list(run_output_dir.glob("*.json"))
    paper_records = list(paper_output_dir.glob("*.json"))
    assert result.exit_code == 0
    assert "Scheduled runs: 2" in result.output
    assert len(run_records) == 2
    assert len(paper_records) == 2

    paper_payloads = [
        json.loads(path.read_text()) for path in sorted(paper_records)
    ]
    assert paper_payloads[0]["snapshot"]["cash"] == 80
    assert paper_payloads[1]["snapshot"]["cash"] == 60


def test_schedule_paper_order_rejects_invalid_iterations(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "schedule",
            "paper-order",
            "--iterations",
            "0",
            "--run-output-dir",
            str(tmp_path / "scheduler"),
            "--paper-output-dir",
            str(tmp_path / "paper"),
        ],
    )

    assert result.exit_code == 2
    assert "iterations must be at least 1" in result.output
