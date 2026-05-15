import pandas as pd

from quant.execution import (
    PaperBroker,
    decide_latest_signal,
    execute_latest_signal,
)
from quant.models.execution import PaperSignalAction
from quant.models.market import PriceData
from quant.strategies import MomentumStrategy


def test_decide_latest_signal_returns_buy_for_latest_entry() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    strategy = MomentumStrategy()

    decision = decide_latest_signal(
        prices=prices,
        signals=strategy.generate_signals(prices),
    )

    assert decision.action == PaperSignalAction.BUY
    assert decision.signal_date == "2024-01-25"
    assert decision.market_price == 20


def test_execute_latest_signal_buys_through_paper_broker() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    broker = PaperBroker(initial_cash=1_000)

    record = execute_latest_signal(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=broker,
        quantity=2,
    )

    assert record.decision.action == PaperSignalAction.BUY
    assert record.trade is not None
    assert record.trade.fill is not None
    assert record.trade.fill.quantity == 2
    assert record.snapshot.cash == 960


def test_execute_latest_signal_holds_without_trade() -> None:
    prices = PriceData(symbol="AAPL", frame=_hold_frame())
    broker = PaperBroker(initial_cash=1_000)

    record = execute_latest_signal(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=broker,
        quantity=2,
    )

    assert record.decision.action == PaperSignalAction.HOLD
    assert record.trade is None
    assert record.snapshot.cash == 1_000


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
