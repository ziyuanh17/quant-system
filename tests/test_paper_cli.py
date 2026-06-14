"""Test paper cli behavior and safety invariants."""

import json

from typer.testing import CliRunner

from quant.cli import app


def test_paper_order_cli_writes_trade_record(tmp_path) -> None:
    output_dir = tmp_path / "paper"

    result = CliRunner().invoke(
        app,
        [
            "paper",
            "order",
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
            "--output-dir",
            str(output_dir),
        ],
    )

    records = list(output_dir.glob("*.json"))
    assert result.exit_code == 0
    assert "Status: filled" in result.output
    assert len(records) == 1

    payload = json.loads(records[0].read_text())
    assert payload["order"]["request"]["symbol"] == "AAPL"
    assert payload["fill"]["quantity"] == 2
    assert payload["snapshot"]["cash"] == 80


def test_paper_order_cli_exits_nonzero_when_rejected(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "paper",
            "order",
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--initial-cash",
            "50",
            "--output-dir",
            str(tmp_path / "paper"),
        ],
    )

    assert result.exit_code == 1
    assert "Status: rejected" in result.output
    assert "insufficient cash" in result.output
