"""Investigate equivalence between legacy and target simulations."""

from decimal import Decimal
from typing import Any

import pandas as pd

from quant.models.signals import SignalFrame
from quant.models.targets import (
    LegacyEquivalenceReport,
    LegacyEquivalenceStatus,
    StrategyTargetFrame,
    TargetUnit,
)

LEGACY_AVAILABLE_CASH_POLICY = "legacy_available_cash_v1"


def resolve_legacy_available_cash_targets(
    *,
    close: pd.Series,
    signals: SignalFrame,
    initial_cash: float,
    fees: float,
    slippage: float = 0,
    accumulate: bool = False,
) -> StrategyTargetFrame:
    """Resolve current VectorBT signal behavior into observed share targets."""
    portfolio = _legacy_portfolio(
        close=close,
        signals=signals,
        initial_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        accumulate=accumulate,
    )
    return StrategyTargetFrame(
        unit=TargetUnit.SHARES,
        targets=pd.Series(
            [Decimal(str(value)) for value in portfolio.assets()],
            index=close.index,
            dtype=object,
        ),
    )


def investigate_legacy_equivalence(
    *,
    report_id: str,
    strategy_id: str,
    symbol: str,
    scenario_name: str,
    close: pd.Series,
    signals: SignalFrame,
    initial_cash: float,
    fees: float,
    slippage: float = 0,
    accumulate: bool = False,
    numeric_tolerance: float = 1e-9,
) -> LegacyEquivalenceReport:
    """Compare signal simulation with replayed target-amount holdings."""
    legacy = _legacy_portfolio(
        close=close,
        signals=signals,
        initial_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        accumulate=accumulate,
    )
    targets = resolve_legacy_available_cash_targets(
        close=close,
        signals=signals,
        initial_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        accumulate=accumulate,
    )
    adapted = _target_portfolio(
        close=close,
        targets=targets,
        initial_cash=initial_cash,
        fees=fees,
        slippage=slippage,
    )
    differences = _portfolio_differences(
        legacy=legacy,
        adapted=adapted,
        tolerance=numeric_tolerance,
    )
    return LegacyEquivalenceReport(
        report_id=report_id,
        strategy_id=strategy_id,
        symbol=symbol,
        sizing_policy_version=LEGACY_AVAILABLE_CASH_POLICY,
        scenario_name=scenario_name,
        status=(
            LegacyEquivalenceStatus.EQUIVALENT
            if not differences
            else LegacyEquivalenceStatus.NOT_EQUIVALENT
        ),
        numeric_tolerance=numeric_tolerance,
        baseline_total_return=float(legacy.total_return()),
        adapted_total_return=float(adapted.total_return()),
        baseline_final_value=float(legacy.final_value()),
        adapted_final_value=float(adapted.final_value()),
        baseline_trade_count=len(legacy.trades.records_readable),
        adapted_trade_count=len(adapted.trades.records_readable),
        differences=tuple(differences),
    )


def _legacy_portfolio(
    *,
    close: pd.Series,
    signals: SignalFrame,
    initial_cash: float,
    fees: float,
    slippage: float,
    accumulate: bool,
) -> Any:
    import vectorbt as vbt

    return vbt.Portfolio.from_signals(
        close=close,
        entries=signals.entries,
        exits=signals.exits,
        init_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        accumulate=accumulate,
        freq="1D",
    )


def _target_portfolio(
    *,
    close: pd.Series,
    targets: StrategyTargetFrame,
    initial_cash: float,
    fees: float,
    slippage: float,
) -> Any:
    import vectorbt as vbt

    return vbt.Portfolio.from_orders(
        close=close,
        size=targets.targets.astype(float),
        size_type="targetamount",
        init_cash=initial_cash,
        fees=fees,
        slippage=slippage,
        freq="1D",
    )


def _portfolio_differences(*, legacy, adapted, tolerance: float) -> list[str]:
    differences: list[str] = []
    comparisons = {
        "total_return": (legacy.total_return(), adapted.total_return()),
        "final_value": (legacy.final_value(), adapted.final_value()),
    }
    for label, (left, right) in comparisons.items():
        if abs(float(left) - float(right)) > tolerance:
            differences.append(
                f"{label} differs: baseline={float(left):.12f} "
                f"adapted={float(right):.12f}"
            )
    for label, left, right in (
        ("assets", legacy.assets(), adapted.assets()),
        ("cash", legacy.cash(), adapted.cash()),
        ("value", legacy.value(), adapted.value()),
    ):
        if not _series_close(left, right, tolerance=tolerance):
            differences.append(f"{label} series differs")
    if not _frames_close(
        legacy.orders.records_readable,
        adapted.orders.records_readable,
        tolerance=tolerance,
    ):
        differences.append("order records differ")
    if not _frames_close(
        legacy.trades.records_readable,
        adapted.trades.records_readable,
        tolerance=tolerance,
    ):
        differences.append("trade records differ")
    return differences


def _series_close(
    left: pd.Series, right: pd.Series, *, tolerance: float
) -> bool:
    if not left.index.equals(right.index):
        return False
    differences = (left.astype(float) - right.astype(float)).abs()
    return bool((differences <= tolerance).all())


def _frames_close(
    left: pd.DataFrame, right: pd.DataFrame, *, tolerance: float
) -> bool:
    if left.shape != right.shape or tuple(left.columns) != tuple(right.columns):
        return False
    for column in left.columns:
        left_values = left[column]
        right_values = right[column]
        if pd.api.types.is_numeric_dtype(left_values):
            difference = (
                left_values.astype(float) - right_values.astype(float)
            ).abs()
            if not bool((difference <= tolerance).all()):
                return False
        elif not left_values.equals(right_values):
            return False
    return True
