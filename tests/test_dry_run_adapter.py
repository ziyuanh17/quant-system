import json

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
