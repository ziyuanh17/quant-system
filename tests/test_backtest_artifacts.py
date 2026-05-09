import json

import pandas as pd

from quant.backtest.artifacts import write_backtest_artifacts
from quant.models.backtest import (
    BacktestConfig,
    BacktestResult,
    PerformanceMetrics,
)


def test_write_backtest_artifacts_creates_summary_and_trades(tmp_path) -> None:
    result = BacktestResult(
        strategy_name="momentum",
        symbol="AAPL",
        config=BacktestConfig(initial_cash=100_000, fees=0.001),
        metrics=PerformanceMetrics(
            total_return=0.12,
            sharpe_ratio=1.3,
            max_drawdown=-0.08,
            total_trades=1,
            final_value=112_000,
        ),
    )
    trades = pd.DataFrame(
        [{"Symbol": "AAPL", "Size": 10, "Entry Price": 100.0}]
    )

    artifacts = write_backtest_artifacts(result, trades, tmp_path)

    summary = json.loads((tmp_path / "summary.json").read_text())
    trades_csv = (tmp_path / "trades.csv").read_text()

    assert summary["strategy_name"] == "momentum"
    assert summary["metrics"]["final_value"] == 112_000
    assert "Entry Price" in trades_csv
    assert artifacts.summary_json.endswith("summary.json")
