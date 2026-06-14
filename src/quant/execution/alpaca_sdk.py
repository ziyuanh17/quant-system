"""Load optional Alpaca SDK types behind a stable boundary."""

from collections.abc import Callable
from dataclasses import dataclass
from importlib import import_module as import_module_from_stdlib
from typing import Any

from quant.execution.alpaca_paper import AlpacaMarketOrderRequest

ALPACA_EXTRA_INSTALL_HINT = (
    "Alpaca SDK is not installed. Install the optional broker extra with "
    '`python -m pip install -e ".[broker-alpaca]"` or '
    "`uv sync --extra broker-alpaca`."
)

ImportModule = Callable[[str], object]


@dataclass(frozen=True)
class AlpacaTradingSdk:
    """Loaded alpaca-py trading classes used by the future client wrapper."""

    TradingClient: type[Any]
    MarketOrderRequest: type[Any]
    OrderSide: type[Any]
    TimeInForce: type[Any]


def load_alpaca_trading_sdk(
    import_module: ImportModule = import_module_from_stdlib,
) -> AlpacaTradingSdk:
    """Load alpaca-py trading classes only when Alpaca code needs them."""
    try:
        trading_client = import_module("alpaca.trading.client")
        trading_enums = import_module("alpaca.trading.enums")
        trading_requests = import_module("alpaca.trading.requests")
    except ModuleNotFoundError as exc:
        if exc.name == "alpaca" or str(exc.name).startswith("alpaca."):
            raise RuntimeError(ALPACA_EXTRA_INSTALL_HINT) from exc
        raise

    return AlpacaTradingSdk(
        TradingClient=_required_type(trading_client, "TradingClient"),
        MarketOrderRequest=_required_type(
            trading_requests,
            "MarketOrderRequest",
        ),
        OrderSide=_required_type(trading_enums, "OrderSide"),
        TimeInForce=_required_type(trading_enums, "TimeInForce"),
    )


def build_alpaca_sdk_market_order_request(
    request: AlpacaMarketOrderRequest,
    *,
    sdk: AlpacaTradingSdk | None = None,
) -> object:
    """Convert the SDK-free request shape into alpaca-py request objects."""
    loaded_sdk = sdk or load_alpaca_trading_sdk()
    return loaded_sdk.MarketOrderRequest(
        symbol=request.symbol,
        qty=request.qty,
        side=loaded_sdk.OrderSide(request.side),
        time_in_force=loaded_sdk.TimeInForce(request.time_in_force),
        client_order_id=request.client_order_id,
    )


def _required_type(module: object, name: str) -> type[Any]:
    value = getattr(module, name, None)
    if not isinstance(value, type):
        raise RuntimeError(f"alpaca-py module is missing {name}")
    return value
