from typing import Any, cast

import pandas as pd

from quant.execution.broker_adapter import (
    DryRunBrokerAdapter,
    SignalExecutionBroker,
)
from quant.models.execution import (
    DryRunOrderRecord,
    LiveAccountSnapshot,
    OrderRequest,
    OrderSide,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
    TargetPositionPlan,
    TradingSafetyCheck,
)
from quant.models.market import PriceData
from quant.models.signals import SignalFrame
from quant.strategies.base import Strategy


def decide_latest_signal(
    *,
    strategy_name: str,
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
        action = PaperSignalAction.BUY
        return PaperSignalDecision(
            symbol=prices.symbol,
            action=action,
            signal_date=signal_date,
            market_price=market_price,
            reason="latest strategy signal is entry",
            idempotency_key=_signal_key(
                strategy_name, prices.symbol, signal_date, action
            ),
        )
    if latest_exit:
        action = PaperSignalAction.SELL
        return PaperSignalDecision(
            symbol=prices.symbol,
            action=action,
            signal_date=signal_date,
            market_price=market_price,
            reason="latest strategy signal is exit",
            idempotency_key=_signal_key(
                strategy_name, prices.symbol, signal_date, action
            ),
        )
    action = PaperSignalAction.HOLD
    return PaperSignalDecision(
        symbol=prices.symbol,
        action=action,
        signal_date=signal_date,
        market_price=market_price,
        reason="latest strategy signal is hold",
        idempotency_key=_signal_key(
            strategy_name, prices.symbol, signal_date, action
        ),
    )


def plan_target_position_order(
    *,
    decision: PaperSignalDecision,
    account: LiveAccountSnapshot,
    target_long_quantity: int,
) -> TargetPositionPlan:
    """Translate long-only signal intent into an order toward its target."""
    if target_long_quantity < 1:
        raise ValueError("target_long_quantity must be at least 1")

    current_quantity = next(
        (
            position.quantity
            for position in account.positions
            if position.symbol == decision.symbol
        ),
        0,
    )
    if decision.action == PaperSignalAction.HOLD:
        return TargetPositionPlan(
            symbol=decision.symbol,
            signal_action=decision.action,
            current_quantity=current_quantity,
            target_quantity=current_quantity,
            reason="hold signal leaves position unchanged",
        )
    target_quantity = (
        target_long_quantity
        if decision.action == PaperSignalAction.BUY
        else 0
    )
    quantity_delta = target_quantity - current_quantity
    if quantity_delta == 0:
        return TargetPositionPlan(
            symbol=decision.symbol,
            signal_action=decision.action,
            current_quantity=current_quantity,
            target_quantity=target_quantity,
            reason="strategy target position is already satisfied",
        )
    return TargetPositionPlan(
        symbol=decision.symbol,
        signal_action=decision.action,
        current_quantity=current_quantity,
        target_quantity=target_quantity,
        order_request=OrderRequest(
            symbol=decision.symbol,
            side=OrderSide.BUY if quantity_delta > 0 else OrderSide.SELL,
            quantity=abs(quantity_delta),
        ),
        reason="order required to reach strategy target position",
    )


def execute_latest_signal(
    *,
    strategy: Strategy,
    prices: PriceData,
    broker: SignalExecutionBroker,
    quantity: int,
) -> PaperSignalRecord:
    signals = strategy.generate_signals(prices)
    decision = decide_latest_signal(
        strategy_name=strategy.name,
        prices=prices,
        signals=signals,
    )

    if decision.action == PaperSignalAction.HOLD:
        return PaperSignalRecord(
            decision=decision,
            trade=None,
            snapshot=broker.snapshot(),
        )
    if broker.has_processed_signal(decision.idempotency_key):
        return PaperSignalRecord(
            decision=PaperSignalDecision(
                symbol=decision.symbol,
                action=decision.action,
                signal_date=decision.signal_date,
                market_price=decision.market_price,
                reason=(
                    "signal already processed; skipping duplicate paper order"
                ),
                idempotency_key=decision.idempotency_key,
            ),
            trade=None,
            snapshot=broker.snapshot(),
            skipped=True,
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
    broker.mark_signal_processed(decision.idempotency_key)
    return PaperSignalRecord(
        decision=decision,
        trade=trade,
        snapshot=trade.snapshot,
    )


def execute_latest_signal_dry_run(
    *,
    strategy: Strategy,
    prices: PriceData,
    broker: DryRunBrokerAdapter,
    quantity: int,
    safety_check: TradingSafetyCheck,
) -> tuple[PaperSignalDecision, DryRunOrderRecord | None]:
    """Convert the latest signal into a would-submit broker order."""
    signals = strategy.generate_signals(prices)
    decision = decide_latest_signal(
        strategy_name=strategy.name,
        prices=prices,
        signals=signals,
    )

    if decision.action == PaperSignalAction.HOLD:
        return decision, None

    side = (
        OrderSide.BUY
        if decision.action == PaperSignalAction.BUY
        else OrderSide.SELL
    )
    record = broker.submit_market_order(
        OrderRequest(symbol=decision.symbol, side=side, quantity=quantity),
        market_price=decision.market_price,
        safety_check=safety_check,
    )
    return decision, record


def _signal_key(
    strategy_name: str,
    symbol: str,
    signal_date: str,
    action: PaperSignalAction,
) -> str:
    return f"{strategy_name}:{symbol}:{signal_date}:{action.value}"
