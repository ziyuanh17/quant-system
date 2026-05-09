from pathlib import Path
from typing import Any

import pandas as pd

from quant.models.backtest import BacktestArtifactPaths, BacktestResult


def write_backtest_artifacts(
    result: BacktestResult,
    trades: pd.DataFrame,
    output_dir: Path,
) -> BacktestArtifactPaths:
    output_dir.mkdir(parents=True, exist_ok=True)

    summary_path = output_dir / "summary.json"
    trades_path = output_dir / "trades.csv"

    summary_path.write_text(result.model_dump_json(indent=2) + "\n")
    trades.to_csv(trades_path, index=False)

    return BacktestArtifactPaths(
        output_dir=str(output_dir),
        summary_json=str(summary_path),
        trades_csv=str(trades_path),
    )


def readable_trades(portfolio: Any) -> pd.DataFrame:
    trades = portfolio.trades.records_readable
    if isinstance(trades, pd.DataFrame):
        return trades
    return pd.DataFrame(trades)
