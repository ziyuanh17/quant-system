import pandas as pd

from quant.execution import (
    DryRunBrokerAdapter,
    PaperBrokerAdapter,
    decide_latest_signal,
    evaluate_trading_safety,
    execute_latest_signal,
    execute_latest_signal_dry_run,
)
from quant.models.execution import (
    BrokerMode,
    PaperSignalAction,
    TradingMode,
    TradingSafetyConfig,
)
from quant.models.market import PriceData
from quant.strategies import MomentumStrategy


def test_decide_latest_signal_returns_buy_for_latest_entry() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    strategy = MomentumStrategy()

    decision = decide_latest_signal(
        strategy_name=strategy.name,
        prices=prices,
        signals=strategy.generate_signals(prices),
    )

    assert decision.action == PaperSignalAction.BUY
    assert decision.signal_date == "2024-01-25"
    assert decision.market_price == 20
    assert decision.idempotency_key == "momentum:AAPL:2024-01-25:buy"


def test_execute_latest_signal_buys_through_paper_broker() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    broker = PaperBrokerAdapter.from_initial_cash(initial_cash=1_000)

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
    assert broker.state().processed_signal_keys == (
        "momentum:AAPL:2024-01-25:buy",
    )


def test_execute_latest_signal_can_use_paper_broker_adapter() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    adapter = PaperBrokerAdapter.from_initial_cash(initial_cash=1_000)

    record = execute_latest_signal(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=adapter,
        quantity=2,
    )

    account = adapter.account_snapshot()
    assert account.mode == BrokerMode.PAPER
    assert record.trade is not None
    assert account.portfolio.cash == 960
    assert adapter.state().processed_signal_keys == (
        "momentum:AAPL:2024-01-25:buy",
    )


def test_execute_latest_signal_skips_duplicate_trade() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    broker = PaperBrokerAdapter.from_initial_cash(initial_cash=1_000)
    strategy = MomentumStrategy()

    first = execute_latest_signal(
        strategy=strategy,
        prices=prices,
        broker=broker,
        quantity=2,
    )
    second = execute_latest_signal(
        strategy=strategy,
        prices=prices,
        broker=broker,
        quantity=2,
    )

    assert first.trade is not None
    assert second.trade is None
    assert second.skipped
    assert second.snapshot.cash == 960
    assert "already processed" in second.decision.reason


def test_execute_latest_signal_holds_without_trade() -> None:
    prices = PriceData(symbol="AAPL", frame=_hold_frame())
    broker = PaperBrokerAdapter.from_initial_cash(initial_cash=1_000)

    record = execute_latest_signal(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=broker,
        quantity=2,
    )

    assert record.decision.action == PaperSignalAction.HOLD
    assert record.trade is None
    assert record.snapshot.cash == 1_000


def test_execute_latest_signal_dry_run_records_actionable_order() -> None:
    prices = PriceData(symbol="AAPL", frame=_entry_frame())
    check = evaluate_trading_safety(
        TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    )

    decision, record = execute_latest_signal_dry_run(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=DryRunBrokerAdapter(broker_name="example-broker"),
        quantity=2,
        safety_check=check,
    )

    assert decision.action == PaperSignalAction.BUY
    assert record is not None
    assert record.request.symbol == "AAPL"
    assert record.request.side == "buy"
    assert record.request.quantity == 2
    assert record.market_price == 20
    assert record.notional == 40


def test_execute_latest_signal_dry_run_holds_without_order() -> None:
    prices = PriceData(symbol="AAPL", frame=_hold_frame())
    check = evaluate_trading_safety(
        TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    )

    decision, record = execute_latest_signal_dry_run(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=DryRunBrokerAdapter(broker_name="example-broker"),
        quantity=2,
        safety_check=check,
    )

    assert decision.action == PaperSignalAction.HOLD
    assert record is None


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
