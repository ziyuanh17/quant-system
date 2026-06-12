from typing import Any, cast

import pandas as pd

from quant.backtest.artifacts import readable_trades
from quant.models.backtest import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
)
from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.targets import StrategyTargetFrame
from quant.strategies.base import FeatureTargetStrategy, TargetStrategy


class VectorBTTargetBacktester:
    """Research simulator for native target-amount strategies."""

    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run_with_trades(
        self,
        strategy: TargetStrategy,
        prices: PriceData,
    ) -> tuple[BacktestResult, pd.DataFrame, StrategyTargetFrame]:
        targets = strategy.generate_targets(prices)
        portfolio = self._portfolio(close=prices.close, targets=targets)
        return (
            self._result(strategy.name, prices.symbol, portfolio),
            readable_trades(portfolio),
            targets,
        )

    def run_feature_with_trades(
        self,
        strategy: FeatureTargetStrategy,
        features: FeatureData,
    ) -> tuple[BacktestResult, pd.DataFrame, StrategyTargetFrame]:
        targets = strategy.generate_targets_from_features(features)
        portfolio = self._portfolio(close=features.close, targets=targets)
        return (
            self._result(strategy.name, features.symbol, portfolio),
            readable_trades(portfolio),
            targets,
        )

    def run_resolved_targets(
        self,
        *,
        strategy_name: str,
        symbol: str,
        close: pd.Series,
        targets: StrategyTargetFrame,
    ) -> tuple[BacktestResult, pd.DataFrame]:
        portfolio = self._portfolio(close=close, targets=targets)
        return self._result(strategy_name, symbol, portfolio), readable_trades(
            portfolio
        )

    def _portfolio(
        self, *, close: pd.Series, targets: StrategyTargetFrame
    ) -> Any:
        if not targets.targets.index.equals(close.index):
            raise ValueError("targets and close must share the same index")
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise RuntimeError(
                "VectorBT is required for target backtests"
            ) from exc
        return vbt.Portfolio.from_orders(
            close=close,
            size=targets.targets.astype(float),
            size_type="targetamount",
            fees=self.config.fees,
            init_cash=self.config.initial_cash,
            freq=self.config.frequency,
        )

    def _result(
        self, strategy_name: str, symbol: str, portfolio: Any
    ) -> BacktestResult:
        metrics = PerformanceMetrics(
            total_return=float(portfolio.total_return()),
            sharpe_ratio=_optional_float(portfolio.sharpe_ratio()),
            max_drawdown=_optional_float(portfolio.max_drawdown()),
            total_trades=len(portfolio.trades.records_readable),
            final_value=float(portfolio.final_value()),
        )
        return BacktestResult(
            strategy_name=strategy_name,
            symbol=symbol,
            config=self.config,
            metrics=metrics,
        )


def _optional_float(value: object) -> float | None:
    return None if value is None else float(cast(Any, value))
