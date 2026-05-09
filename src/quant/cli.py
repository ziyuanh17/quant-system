from pathlib import Path
from typing import Annotated

import typer

from quant.backtest import VectorBTBacktester
from quant.data import load_price_csv
from quant.models.backtest import BacktestConfig
from quant.strategies import MomentumStrategy

app = typer.Typer(no_args_is_help=True)


@app.callback()
def main() -> None:
    """Quant research and trading CLI."""


@app.command()
def backtest(
    strategy: Annotated[
        str, typer.Option(help="Strategy name to run.")
    ] = "momentum",
    data: Annotated[
        Path,
        typer.Option(help="CSV file with OHLCV data."),
    ] = Path("data/sample_prices.csv"),
    symbol: Annotated[str, typer.Option(help="Symbol to backtest.")] = "AAPL",
    initial_cash: Annotated[
        float, typer.Option(help="Initial cash.")
    ] = 100_000,
    fees: Annotated[
        float, typer.Option(help="Proportional fee per trade.")
    ] = 0.001,
) -> None:
    """Run a VectorBT-backed signal backtest."""
    if strategy != "momentum":
        raise typer.BadParameter(
            "Only the momentum strategy is scaffolded right now."
        )

    prices = load_price_csv(data, symbol)
    result = VectorBTBacktester(
        BacktestConfig(initial_cash=initial_cash, fees=fees)
    ).run(MomentumStrategy(), prices)

    metrics = result.metrics
    typer.echo(f"Strategy: {result.strategy_name}")
    typer.echo(f"Symbol: {result.symbol}")
    typer.echo(f"Initial cash: {result.config.initial_cash:,.2f}")
    typer.echo(f"Final value: {metrics.final_value:,.2f}")
    typer.echo(f"Total return: {metrics.total_return:.2%}")
    typer.echo(f"Sharpe ratio: {_format_optional(metrics.sharpe_ratio)}")
    typer.echo(
        f"Max drawdown: {_format_optional(metrics.max_drawdown, percent=True)}"
    )
    typer.echo(f"Trades: {metrics.total_trades}")


def _format_optional(value: float | None, *, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if percent:
        return f"{value:.2%}"
    return f"{value:.2f}"


if __name__ == "__main__":
    app()
