from pydantic import Field

from quant.models.base import FrozenModel


class BacktestConfig(FrozenModel):
    initial_cash: float = Field(default=100_000, gt=0)
    fees: float = Field(default=0.001, ge=0)
    frequency: str = "1D"


class PerformanceMetrics(FrozenModel):
    total_return: float
    sharpe_ratio: float | None = None
    max_drawdown: float | None = None
    total_trades: int
    final_value: float


class BacktestResult(FrozenModel):
    strategy_name: str
    symbol: str
    config: BacktestConfig
    metrics: PerformanceMetrics


class BacktestArtifactPaths(FrozenModel):
    output_dir: str
    summary_json: str
    trades_csv: str
