from typing import Any

import pandas as pd

from quant.backtest.artifacts import readable_trades
from quant.models.backtest import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
)
from quant.models.market import PriceData
from quant.strategies.base import Strategy


class VectorBTBacktester:
    def __init__(self, config: BacktestConfig | None = None) -> None:
        self.config = config or BacktestConfig()

    def run(self, strategy: Strategy, prices: PriceData) -> BacktestResult:
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise RuntimeError(
                "VectorBT is not installed. Install dependencies with "
                '`python -m pip install -e ".[dev]"` and try again.'
            ) from exc

        signals = strategy.generate_signals(prices)
        portfolio = vbt.Portfolio.from_signals(
            close=prices.close,
            entries=signals.entries,
            exits=signals.exits,
            init_cash=self.config.initial_cash,
            fees=self.config.fees,
            freq=self.config.frequency,
        )

        metrics = PerformanceMetrics(
            total_return=_call_metric(portfolio, "total_return"),
            sharpe_ratio=_optional_metric(portfolio, "sharpe_ratio"),
            max_drawdown=_optional_metric(portfolio, "max_drawdown"),
            total_trades=_trade_count(portfolio),
            final_value=_call_metric(portfolio, "final_value"),
        )
        return BacktestResult(
            strategy_name=strategy.name,
            symbol=prices.symbol,
            config=self.config,
            metrics=metrics,
        )

    def run_with_trades(
        self, strategy: Strategy, prices: PriceData
    ) -> tuple[BacktestResult, pd.DataFrame]:
        try:
            import vectorbt as vbt
        except ImportError as exc:
            raise RuntimeError(
                "VectorBT is not installed. Install dependencies with "
                '`python -m pip install -e ".[dev]"` and try again.'
            ) from exc

        signals = strategy.generate_signals(prices)
        portfolio = vbt.Portfolio.from_signals(
            close=prices.close,
            entries=signals.entries,
            exits=signals.exits,
            init_cash=self.config.initial_cash,
            fees=self.config.fees,
            freq=self.config.frequency,
        )

        metrics = PerformanceMetrics(
            total_return=_call_metric(portfolio, "total_return"),
            sharpe_ratio=_optional_metric(portfolio, "sharpe_ratio"),
            max_drawdown=_optional_metric(portfolio, "max_drawdown"),
            total_trades=_trade_count(portfolio),
            final_value=_call_metric(portfolio, "final_value"),
        )
        result = BacktestResult(
            strategy_name=strategy.name,
            symbol=prices.symbol,
            config=self.config,
            metrics=metrics,
        )
        return result, readable_trades(portfolio)


def _call_metric(portfolio: Any, method_name: str) -> float:
    method = getattr(portfolio, method_name)
    return float(method())


def _optional_metric(portfolio: Any, method_name: str) -> float | None:
    method = getattr(portfolio, method_name, None)
    if method is None:
        return None
    value = method()
    return None if value is None else float(value)


def _trade_count(portfolio: Any) -> int:
    records = portfolio.trades.records_readable
    return len(records)
