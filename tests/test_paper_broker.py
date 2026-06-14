"""Test paper broker behavior and safety invariants."""

from quant.execution import PaperBroker, check_order_risk
from quant.models.execution import OrderRequest, OrderSide, RiskDecision


def test_paper_broker_fills_buy_and_updates_snapshot() -> None:
    broker = PaperBroker(initial_cash=1_000)

    record = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=5),
        market_price=20,
    )

    assert record.fill is not None
    assert record.snapshot.cash == 900
    assert record.snapshot.equity == 1_000
    assert record.snapshot.positions[0].quantity == 5
    assert record.snapshot.positions[0].average_price == 20


def test_paper_broker_rejects_buy_without_cash() -> None:
    broker = PaperBroker(initial_cash=50)

    record = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=10),
        market_price=20,
    )

    assert record.fill is None
    assert record.order.risk.decision == RiskDecision.REJECTED
    assert record.order.risk.reason == "insufficient cash"
    assert record.snapshot.cash == 50
    assert record.snapshot.positions == ()


def test_paper_broker_sell_reduces_position() -> None:
    broker = PaperBroker(initial_cash=1_000)
    broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=5),
        market_price=20,
    )

    record = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        market_price=25,
    )

    assert record.fill is not None
    assert record.snapshot.cash == 950
    assert record.snapshot.positions[0].quantity == 3
    assert record.snapshot.positions[0].last_price == 25


def test_risk_rejects_sell_without_position() -> None:
    result = check_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=1),
        cash=1_000,
        positions={},
        market_price=20,
    )

    assert not result.approved
    assert result.reason == "insufficient position quantity"
