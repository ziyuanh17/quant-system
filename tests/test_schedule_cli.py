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

    paper_payloads = sorted(
        [json.loads(path.read_text()) for path in paper_records],
        key=lambda payload: payload["order"]["created_at"],
    )
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


def test_schedule_paper_signal_writes_signal_record(tmp_path) -> None:
    data = tmp_path / "prices.csv"
    _write_entry_prices(data)
    run_output_dir = tmp_path / "scheduler"
    signal_output_dir = tmp_path / "signals"

    result = CliRunner().invoke(
        app,
        [
            "schedule",
            "paper-signal",
            "--data",
            str(data),
            "--symbol",
            "AAPL",
            "--quantity",
            "2",
            "--initial-cash",
            "1000",
            "--iterations",
            "1",
            "--run-output-dir",
            str(run_output_dir),
            "--signal-output-dir",
            str(signal_output_dir),
        ],
    )

    signal_records = list(signal_output_dir.glob("*.json"))
    run_records = list(run_output_dir.glob("*.json"))
    assert result.exit_code == 0
    assert "Scheduled runs: 1" in result.output
    assert len(signal_records) == 1
    assert len(run_records) == 1

    payload = json.loads(signal_records[0].read_text())
    assert payload["decision"]["action"] == "buy"
    assert payload["trade"]["fill"]["quantity"] == 2
    assert payload["snapshot"]["cash"] == 960


def _write_entry_prices(path) -> None:
    closes = [10.0] * 19 + [8.0] * 5 + [20.0]
    rows = ["date,symbol,open,high,low,close,volume"]
    for index, close in enumerate(closes, start=1):
        rows.append(
            f"2024-01-{index:02d},AAPL,{close},{close + 1},"
            f"{close - 1},{close},100"
        )
    path.write_text("\n".join(rows))
