from types import SimpleNamespace
from typing import Any, cast

import pytest

from quant.execution.alpaca_paper import (
    AlpacaPaperBrokerClient,
    AlpacaPaperConfig,
)
from quant.execution.alpaca_sdk import AlpacaTradingSdk
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)


def test_alpaca_paper_config_requires_credentials() -> None:
    with pytest.raises(ValueError, match="api_key"):
        AlpacaPaperConfig(
            api_key="",
            secret_key="paper-secret",
            account_id="acct-1",
        )


def test_alpaca_paper_client_constructs_sdk_client_in_paper_mode() -> None:
    config = AlpacaPaperConfig(
        api_key="paper-key",
        secret_key="paper-secret",
        account_id="acct-1",
        url_override="https://example.test",
    )

    client = AlpacaPaperBrokerClient(config=config, sdk=_fake_sdk())

    trading_client = client.trading_client_for_testing
    assert isinstance(trading_client, FakeTradingClient)
    assert trading_client.init_kwargs == {
        "api_key": "paper-key",
        "secret_key": "paper-secret",
        "paper": True,
        "url_override": "https://example.test",
    }


def test_alpaca_paper_client_can_use_injected_trading_client() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )

    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    assert client.trading_client_for_testing is trading_client


def test_alpaca_paper_client_submits_market_order_and_maps_fill() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100.25,
        client_order_id="client-1",
        safety_check=_allowed_live_check(),
    )

    assert isinstance(trading_client.submitted_orders[0], FakeMarketOrder)
    assert trading_client.submitted_orders[0].kwargs["symbol"] == "AAPL"
    assert trading_client.submitted_orders[0].kwargs["side"].value == "buy"
    assert record.status == LiveOrderStatus.FILLED
    assert record.broker_name == "alpaca-paper"
    assert record.account_id == "acct-1"
    assert record.notional == 200.5
    assert len(client.fills()) == 1
    assert client.fills()[0].client_order_id == "client-1"
    assert client.fills()[0].notional == 200.5


def test_alpaca_paper_client_maps_account_snapshot() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.account = SimpleNamespace(
        id="acct-1",
        cash="1000.25",
        buying_power="2000.50",
    )
    trading_client.positions = [
        SimpleNamespace(
            symbol="AAPL",
            qty="2",
            avg_entry_price="100.25",
            current_price="101.50",
        ),
    ]
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    snapshot = client.account_snapshot()

    assert snapshot.broker_name == "alpaca-paper"
    assert snapshot.account_id == "acct-1"
    assert snapshot.cash == 1000.25
    assert snapshot.buying_power == 2000.5
    assert snapshot.positions[0].symbol == "AAPL"


def test_alpaca_paper_client_open_orders_maps_known_orders_only() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.next_order_status = "accepted"
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )

    client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="client-1",
        safety_check=_allowed_live_check(),
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="unknown-order",
            client_order_id="unknown-client-id",
            status="accepted",
        )
    )

    open_orders = client.open_orders()

    assert len(open_orders) == 1
    assert open_orders[0].client_order_id == "client-1"
    assert open_orders[0].status == LiveOrderStatus.ACCEPTED


def test_alpaca_paper_client_detects_unknown_open_broker_orders() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="unknown-order",
            client_order_id="unknown-client-id",
            status="accepted",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    assert client.has_open_orders() is True


def test_alpaca_paper_client_refreshes_known_fills_from_polled_orders() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)
    order_record = LiveOrderRecord(
        client_order_id="client-1",
        broker_order_id="alpaca-order-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=request,
        reference_price=100.25,
        notional=200.5,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.FILLED,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="alpaca-order-1",
            client_order_id="client-1",
            status="filled",
            filled_qty="2",
            filled_avg_price="100.25",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    client.remember_order_record(order_record)
    fills = client.fills()

    assert len(fills) == 1
    assert fills[0].client_order_id == "client-1"
    assert fills[0].notional == 200.5


def test_alpaca_paper_client_refreshes_terminal_order_by_broker_id() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1)
    order_record = LiveOrderRecord(
        client_order_id="client-1",
        broker_order_id="alpaca-order-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=request,
        reference_price=100,
        notional=100,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.ACCEPTED,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="alpaca-order-1",
            client_order_id="client-1",
            status="canceled",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    client.remember_order_record(order_record)
    refreshed = client.refresh_order_record(order_record)

    assert refreshed.id == order_record.id
    assert refreshed.status == LiveOrderStatus.CANCELLED
    assert refreshed.client_order_id == "client-1"
    assert refreshed.broker_order_id == "alpaca-order-1"


class FakeEnum:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeMarketOrder:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeTradingClient:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        paper: bool,
        url_override: str | None = None,
    ) -> None:
        self.init_kwargs = {
            "api_key": api_key,
            "secret_key": secret_key,
            "paper": paper,
            "url_override": url_override,
        }
        self.submitted_orders: list[object] = []
        self.orders: list[object] = []
        self.positions: list[object] = []
        self.account = SimpleNamespace(
            id="acct-1",
            cash="1000",
            buying_power="1000",
        )
        self.next_order_status = "filled"

    def submit_order(self, order_data: object) -> object:
        if not isinstance(order_data, FakeMarketOrder):
            raise TypeError("expected FakeMarketOrder")
        self.submitted_orders.append(order_data)
        order = SimpleNamespace(
            id=f"alpaca-order-{len(self.orders) + 1}",
            client_order_id=order_data.kwargs["client_order_id"],
            status=self.next_order_status,
            filled_qty=str(order_data.kwargs["qty"]),
            filled_avg_price="100.25",
        )
        self.orders.append(order)
        return order

    def get_orders(self, filter: object | None = None) -> list[object]:
        return self.orders

    def get_order_by_id(self, order_id: str) -> object:
        for order in self.orders:
            order_id_value = cast(Any, order).id
            if order_id_value == order_id:
                return order
        raise ValueError(f"unknown order: {order_id}")

    def get_account(self) -> object:
        return self.account

    def get_all_positions(self) -> list[object]:
        return self.positions


def _fake_sdk() -> AlpacaTradingSdk:
    return AlpacaTradingSdk(
        TradingClient=FakeTradingClient,
        MarketOrderRequest=FakeMarketOrder,
        OrderSide=FakeEnum,
        TimeInForce=FakeEnum,
    )


def _allowed_live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)
