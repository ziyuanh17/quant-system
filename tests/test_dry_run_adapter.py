import json
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.execution import DryRunBrokerAdapter, evaluate_trading_safety
from quant.models.execution import (
    DryRunOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyConfig,
)


def test_dry_run_adapter_records_would_submit_order() -> None:
    check = evaluate_trading_safety(
        TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    )
    adapter = DryRunBrokerAdapter(broker_name="example-broker")

    record = adapter.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=3),
        market_price=25,
        safety_check=check,
    )

    assert record.status == DryRunOrderStatus.WOULD_SUBMIT
    assert record.trading_mode == TradingMode.DRY_RUN
    assert record.broker_name == "example-broker"
    assert record.notional == 75
    assert record.safety_check.allowed


def test_dry_run_adapter_rejects_non_dry_run_safety_check() -> None:
    check = evaluate_trading_safety(TradingSafetyConfig())
    adapter = DryRunBrokerAdapter(broker_name="example-broker")

    with pytest.raises(ValueError, match="dry-run orders require"):
        adapter.submit_market_order(
            OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
            market_price=25,
            safety_check=check,
        )


def test_dry_run_order_cli_writes_intended_order_record(tmp_path) -> None:
    output_dir = tmp_path / "dry_run" / "orders"

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "order",
            "--symbol",
            "MSFT",
            "--side",
            "sell",
            "--quantity",
            "4",
            "--price",
            "12.5",
            "--broker-name",
            "example-broker",
            "--output-dir",
            str(output_dir),
        ],
    )

    records = list(output_dir.glob("*.json"))
    payload = json.loads(records[0].read_text())
    assert result.exit_code == 0
    assert "Status: would_submit" in result.output
    assert len(records) == 1
    assert payload["status"] == "would_submit"
    assert payload["trading_mode"] == "dry_run"
    assert payload["broker_name"] == "example-broker"
    assert payload["request"]["symbol"] == "MSFT"
    assert payload["request"]["side"] == "sell"
    assert payload["request"]["quantity"] == 4
    assert payload["market_price"] == 12.5
    assert payload["notional"] == 50
    assert "fill" not in payload
    assert "snapshot" not in payload


def test_dry_run_signal_cli_writes_order_for_buy_signal(tmp_path) -> None:
    data = tmp_path / "prices.csv"
    _entry_frame().to_csv(data, index=False)
    output_dir = tmp_path / "dry_run" / "orders"

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "signal",
            "--data",
            str(data),
            "--symbol",
            "AAPL",
            "--quantity",
            "2",
            "--broker-name",
            "example-broker",
            "--output-dir",
            str(output_dir),
        ],
    )

    records = list(output_dir.glob("*.json"))
    payload = json.loads(records[0].read_text())
    assert result.exit_code == 0
    assert "Signal: buy" in result.output
    assert "Status: would_submit" in result.output
    assert len(records) == 1
    assert payload["request"]["symbol"] == "AAPL"
    assert payload["request"]["side"] == "buy"
    assert payload["request"]["quantity"] == 2
    assert payload["market_price"] == 20
    assert payload["notional"] == 40


def test_dry_run_signal_cli_writes_no_order_for_hold_signal(tmp_path) -> None:
    data = tmp_path / "prices.csv"
    _hold_frame().to_csv(data, index=False)
    output_dir = tmp_path / "dry_run" / "orders"

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "signal",
            "--data",
            str(data),
            "--symbol",
            "AAPL",
            "--output-dir",
            str(output_dir),
        ],
    )

    assert result.exit_code == 0
    assert "Signal: hold" in result.output
    assert "Dry-run order: none" in result.output
    assert not output_dir.exists()


def test_dry_run_compare_paper_cli_passes_matching_records(tmp_path) -> None:
    paper_dir = tmp_path / "paper" / "signals"
    dry_run_dir = tmp_path / "dry_run" / "orders"
    report_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    data = tmp_path / "prices.csv"
    _entry_frame().to_csv(data, index=False)
    _run_paper_signal(data, paper_dir)
    _run_dry_run_signal(data, dry_run_dir)

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "compare-paper",
            "--paper-signal-dir",
            str(paper_dir),
            "--dry-run-order-dir",
            str(dry_run_dir),
            "--output-path",
            str(report_path),
        ],
    )

    payload = json.loads(report_path.read_text())
    assert result.exit_code == 0
    assert "Status: passed" in result.output
    assert payload["status"] == "passed"
    assert payload["difference_count"] == 0
    assert payload["paper_action"] == "buy"
    assert payload["dry_run_side"] == "buy"


def test_dry_run_compare_paper_cli_fails_quantity_mismatch(
    tmp_path,
) -> None:
    paper_dir = tmp_path / "paper" / "signals"
    dry_run_dir = tmp_path / "dry_run" / "orders"
    report_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    data = tmp_path / "prices.csv"
    _entry_frame().to_csv(data, index=False)
    _run_paper_signal(data, paper_dir, quantity=2)
    _run_dry_run_signal(data, dry_run_dir, quantity=1)

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "compare-paper",
            "--paper-signal-dir",
            str(paper_dir),
            "--dry-run-order-dir",
            str(dry_run_dir),
            "--output-path",
            str(report_path),
        ],
    )

    payload = json.loads(report_path.read_text())
    assert result.exit_code == 1
    assert "Status: failed" in result.output
    assert payload["status"] == "failed"
    assert payload["differences"][0]["field"] == "quantity"


def test_dry_run_compare_paper_cli_passes_hold_without_order(
    tmp_path,
) -> None:
    paper_dir = tmp_path / "paper" / "signals"
    dry_run_dir = tmp_path / "dry_run" / "orders"
    report_path = tmp_path / "dry_run" / "comparison" / "latest.json"
    data = tmp_path / "prices.csv"
    _hold_frame().to_csv(data, index=False)
    _run_paper_signal(data, paper_dir)

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "compare-paper",
            "--paper-signal-dir",
            str(paper_dir),
            "--dry-run-order-dir",
            str(dry_run_dir),
            "--output-path",
            str(report_path),
        ],
    )

    payload = json.loads(report_path.read_text())
    assert result.exit_code == 0
    assert payload["status"] == "passed"
    assert payload["paper_action"] == "hold"
    assert payload["dry_run_side"] is None


def _run_paper_signal(
    data: Path,
    output_dir: Path,
    *,
    quantity: int = 2,
) -> None:
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
            str(quantity),
            "--initial-cash",
            "1000",
            "--iterations",
            "1",
            "--signal-output-dir",
            str(output_dir),
            "--state-path",
            str(output_dir.parent / "state.json"),
            "--run-output-dir",
            str(output_dir.parent / "runs"),
        ],
    )
    assert result.exit_code == 0


def _run_dry_run_signal(
    data: Path,
    output_dir: Path,
    *,
    quantity: int = 2,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "signal",
            "--data",
            str(data),
            "--symbol",
            "AAPL",
            "--quantity",
            str(quantity),
            "--output-dir",
            str(output_dir),
        ],
    )
    assert result.exit_code == 0


def _entry_frame() -> pd.DataFrame:
    closes = [10.0] * 19 + [8.0] * 5 + [20.0]
    return _frame_from_closes(closes)


def _hold_frame() -> pd.DataFrame:
    closes = [10.0] * 25
    return _frame_from_closes(closes)


def _frame_from_closes(closes: list[float]) -> pd.DataFrame:
    dates = pd.date_range("2024-01-01", periods=len(closes))
    return pd.DataFrame(
        {
            "date": [timestamp.date() for timestamp in dates],
            "symbol": ["AAPL"] * len(closes),
            "open": closes,
            "high": [close + 1 for close in closes],
            "low": [close - 1 for close in closes],
            "close": closes,
            "volume": [100] * len(closes),
        }
    )
