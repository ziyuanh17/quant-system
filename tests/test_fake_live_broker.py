import pytest

from quant.execution import FakeLiveBrokerClient
from quant.models.execution import (
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    Position,
    TradingMode,
    TradingSafetyCheck,
)


def test_fake_live_broker_fills_buy_and_updates_snapshot() -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="momentum-AAPL-2024-01-25-buy",
        safety_check=_allowed_live_check(),
    )
    snapshot = client.account_snapshot()

    assert record.status == LiveOrderStatus.FILLED
    assert record.broker_order_id == "fake-order-1"
    assert record.notional == 200
    assert len(client.fills()) == 1
    assert client.fills()[0].broker_execution_id == "fake-exec-1"
    assert snapshot.cash == 800
    assert snapshot.positions[0].symbol == "AAPL"
    assert snapshot.positions[0].quantity == 2
    assert snapshot.open_order_ids == ()


def test_fake_live_broker_rejects_buy_without_buying_power() -> None:
    client = FakeLiveBrokerClient(initial_cash=50)

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="too-large-buy",
        safety_check=_allowed_live_check(),
    )

    assert record.status == LiveOrderStatus.REJECTED
    assert record.rejection_reason == "insufficient buying power"
    assert client.fills() == ()
    assert client.account_snapshot().cash == 50


def test_fake_live_broker_rejects_sell_without_position() -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=1),
        reference_price=100,
        client_order_id="missing-position-sell",
        safety_check=_allowed_live_check(),
    )

    assert record.status == LiveOrderStatus.REJECTED
    assert record.rejection_reason == "insufficient position"
    assert client.fills() == ()


def test_fake_live_broker_duplicate_client_order_id_is_idempotent() -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)

    first = client.submit_market_order(
        request,
        reference_price=100,
        client_order_id="duplicate-id",
        safety_check=_allowed_live_check(),
    )
    second = client.submit_market_order(
        request,
        reference_price=100,
        client_order_id="duplicate-id",
        safety_check=_allowed_live_check(),
    )

    assert second == first
    assert len(client.fills()) == 1
    assert client.account_snapshot().cash == 800


def test_fake_live_broker_sells_existing_position() -> None:
    client = FakeLiveBrokerClient(
        initial_cash=100,
        positions=(
            Position(
                symbol="AAPL",
                quantity=2,
                average_price=90,
                last_price=100,
            ),
        ),
    )

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=1),
        reference_price=110,
        client_order_id="sell-existing-position",
        safety_check=_allowed_live_check(),
    )
    snapshot = client.account_snapshot()

    assert record.status == LiveOrderStatus.FILLED
    assert snapshot.cash == 210
    assert snapshot.positions[0].quantity == 1
    assert snapshot.positions[0].last_price == 110


def test_fake_live_broker_requires_allowed_live_check() -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)

    with pytest.raises(ValueError, match="allowed live check"):
        client.submit_market_order(
            OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
            reference_price=100,
            client_order_id="blocked",
            safety_check=TradingSafetyCheck(
                mode=TradingMode.DRY_RUN,
                allowed=True,
            ),
        )


def _allowed_live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)
