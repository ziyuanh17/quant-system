from typing import Any, cast

import pandas as pd

from quant.execution.paper_broker import PaperBroker
from quant.models.execution import (
    OrderRequest,
    OrderSide,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
)
from quant.models.market import PriceData
from quant.models.signals import SignalFrame
from quant.strategies.base import Strategy


def decide_latest_signal(
    *,
    prices: PriceData,
    signals: SignalFrame,
) -> PaperSignalDecision:
    """Convert the latest strategy signal into a paper-trading action."""

    close = prices.close
    latest_timestamp = pd.Timestamp(cast(Any, close.index[-1]))
    signal_date = str(latest_timestamp.date())
    market_price = float(close.iloc[-1])
    latest_entry = bool(cast(pd.Series, signals.entries).iloc[-1])
    latest_exit = bool(cast(pd.Series, signals.exits).iloc[-1])

    if latest_entry:
        return PaperSignalDecision(
            symbol=prices.symbol,
            action=PaperSignalAction.BUY,
            signal_date=signal_date,
            market_price=market_price,
            reason="latest strategy signal is entry",
        )
    if latest_exit:
        return PaperSignalDecision(
            symbol=prices.symbol,
            action=PaperSignalAction.SELL,
            signal_date=signal_date,
            market_price=market_price,
            reason="latest strategy signal is exit",
        )
    return PaperSignalDecision(
        symbol=prices.symbol,
        action=PaperSignalAction.HOLD,
        signal_date=signal_date,
        market_price=market_price,
        reason="latest strategy signal is hold",
    )


def execute_latest_signal(
    *,
    strategy: Strategy,
    prices: PriceData,
    broker: PaperBroker,
    quantity: int,
) -> PaperSignalRecord:
    signals = strategy.generate_signals(prices)
    decision = decide_latest_signal(prices=prices, signals=signals)

    if decision.action == PaperSignalAction.HOLD:
        return PaperSignalRecord(
            decision=decision,
            trade=None,
            snapshot=broker.snapshot(),
        )

    side = (
        OrderSide.BUY
        if decision.action == PaperSignalAction.BUY
        else OrderSide.SELL
    )
    trade = broker.submit_market_order(
        OrderRequest(symbol=decision.symbol, side=side, quantity=quantity),
        market_price=decision.market_price,
    )
    return PaperSignalRecord(
        decision=decision,
        trade=trade,
        snapshot=trade.snapshot,
    )
