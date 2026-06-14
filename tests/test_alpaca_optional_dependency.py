"""Test alpaca optional dependency behavior and safety invariants."""

import subprocess
import sys
from types import SimpleNamespace
from typing import Any

import pytest

from quant.models.execution import OrderRequest, OrderSide


def test_execution_import_does_not_eagerly_import_alpaca_sdk() -> None:
    script = """
import sys
import quant.execution

print(
    any(
        name == "alpaca" or name.startswith("alpaca.")
        for name in sys.modules
    )
)
"""

    result = subprocess.run(
        [sys.executable, "-c", script],
        check=True,
        capture_output=True,
        text=True,
    )

    assert result.stdout.strip() == "False"


def test_missing_alpaca_sdk_error_has_extra_install_hint() -> None:
    from quant.execution.alpaca_sdk import load_alpaca_trading_sdk

    def missing_alpaca(_name: str) -> object:
        raise ModuleNotFoundError(
            "No module named 'alpaca'",
            name="alpaca",
        )

    with pytest.raises(RuntimeError, match="broker-alpaca"):
        load_alpaca_trading_sdk(import_module=missing_alpaca)


def test_load_alpaca_trading_sdk_imports_only_inside_loader() -> None:
    from quant.execution.alpaca_sdk import load_alpaca_trading_sdk

    imported_names: list[str] = []
    fake_modules = {
        "alpaca.trading.client": SimpleNamespace(TradingClient=object),
        "alpaca.trading.enums": SimpleNamespace(
            OrderSide=object,
            TimeInForce=object,
        ),
        "alpaca.trading.requests": SimpleNamespace(
            MarketOrderRequest=object,
        ),
    }

    def fake_import_module(name: str) -> object:
        imported_names.append(name)
        return fake_modules[name]

    sdk = load_alpaca_trading_sdk(import_module=fake_import_module)

    assert sdk.TradingClient is object
    assert sdk.MarketOrderRequest is object
    assert sdk.OrderSide is object
    assert sdk.TimeInForce is object
    assert imported_names == [
        "alpaca.trading.client",
        "alpaca.trading.enums",
        "alpaca.trading.requests",
    ]


def test_build_alpaca_sdk_market_order_request_uses_sdk_shapes() -> None:
    from quant.execution.alpaca_paper import (
        map_order_request_to_alpaca_market_order,
    )
    from quant.execution.alpaca_sdk import (
        AlpacaTradingSdk,
        build_alpaca_sdk_market_order_request,
    )

    class FakeEnum:
        def __init__(self, value: str) -> None:
            self.value = value

    class FakeMarketOrderRequest:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs

    internal_request = OrderRequest(
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=2,
    )
    sdk_free_request = map_order_request_to_alpaca_market_order(
        internal_request,
        client_order_id="client-1",
    )
    sdk = AlpacaTradingSdk(
        TradingClient=object,
        MarketOrderRequest=FakeMarketOrderRequest,
        OrderSide=FakeEnum,
        TimeInForce=FakeEnum,
    )

    built_request = build_alpaca_sdk_market_order_request(
        sdk_free_request,
        sdk=sdk,
    )

    assert isinstance(built_request, FakeMarketOrderRequest)
    assert built_request.kwargs["symbol"] == "AAPL"
    assert built_request.kwargs["qty"] == 2
    assert built_request.kwargs["side"].value == "buy"
    assert built_request.kwargs["time_in_force"].value == "day"
    assert built_request.kwargs["client_order_id"] == "client-1"


def test_installed_alpaca_sdk_import_smoke() -> None:
    pytest.importorskip("alpaca")

    from quant.execution.alpaca_sdk import load_alpaca_trading_sdk

    sdk = load_alpaca_trading_sdk()

    assert sdk.TradingClient.__name__ == "TradingClient"
    assert sdk.MarketOrderRequest.__name__ == "MarketOrderRequest"
