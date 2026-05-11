from pathlib import Path
from typing import Annotated

import typer

from quant.backtest import VectorBTBacktester
from quant.backtest.artifacts import write_backtest_artifacts
from quant.data import (
    YFinanceMarketBarProvider,
    ingest_market_bars,
    load_price_csv,
    validate_market_bars_csv,
)
from quant.models.backtest import BacktestConfig
from quant.models.ingestion import IngestRequest
from quant.models.validation import ValidationReport
from quant.strategies import MomentumStrategy

app = typer.Typer(no_args_is_help=True)
data_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")


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
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory where backtest artifacts are written."),
    ] = Path("data/results/latest"),
) -> None:
    """Run a VectorBT-backed signal backtest."""
    if strategy != "momentum":
        raise typer.BadParameter(
            "Only the momentum strategy is scaffolded right now."
        )

    prices = load_price_csv(data, symbol)
    result, trades = VectorBTBacktester(
        BacktestConfig(initial_cash=initial_cash, fees=fees)
    ).run_with_trades(MomentumStrategy(), prices)
    artifacts = write_backtest_artifacts(result, trades, output_dir)

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
    typer.echo(f"Summary: {artifacts.summary_json}")
    typer.echo(f"Trades CSV: {artifacts.trades_csv}")


@data_app.command("ingest")
def ingest_data(
    symbol: Annotated[str, typer.Option(help="Symbol to ingest.")] = "AAPL",
    start: Annotated[
        str, typer.Option(help="Inclusive start date.")
    ] = "2024-01-01",
    end: Annotated[
        str | None,
        typer.Option(help="Exclusive end date. Omit to fetch through latest."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(help="Data provider name."),
    ] = "yfinance",
    raw_dir: Annotated[
        Path,
        typer.Option(help="Root directory for raw provider data."),
    ] = Path("data/raw"),
    normalized_dir: Annotated[
        Path,
        typer.Option(help="Root directory for normalized data."),
    ] = Path("data/normalized"),
) -> None:
    """Ingest market bars through the data provider interface."""
    if provider != "yfinance":
        raise typer.BadParameter("Only yfinance is implemented right now.")

    request = IngestRequest(symbols=(symbol,), start=start, end=end)
    artifacts = ingest_market_bars(
        YFinanceMarketBarProvider(),
        request,
        raw_root=raw_dir,
        normalized_root=normalized_dir,
    )

    for artifact in artifacts:
        typer.echo(f"Raw: {artifact.raw_path}")
        typer.echo(f"Normalized: {artifact.normalized_path}")


@data_app.command("validate")
def validate_data(
    data: Annotated[
        Path,
        typer.Option(help="Normalized market-bars CSV to validate."),
    ],
    symbol: Annotated[str, typer.Option(help="Expected symbol.")] = "AAPL",
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required for this dataset."),
    ] = 1,
) -> None:
    """Validate normalized market-bar data before using it."""
    report = validate_market_bars_csv(data, symbol, min_rows=min_rows)
    _print_validation_report(report)
    if not report.passed:
        raise typer.Exit(code=1)


def _print_validation_report(report: ValidationReport) -> None:
    status = "passed" if report.passed else "failed"
    typer.echo(f"Dataset: {report.dataset}")
    typer.echo(f"Symbol: {report.symbol}")
    typer.echo(f"Rows: {report.rows}")
    typer.echo(f"Status: {status}")
    typer.echo(f"Issues: {report.issue_count}")

    for issue in report.issues:
        location = []
        if issue.row is not None:
            location.append(f"row={issue.row}")
        if issue.field is not None:
            location.append(f"field={issue.field}")
        suffix = f" ({', '.join(location)})" if location else ""
        typer.echo(
            f"[{issue.severity}] {issue.code}: {issue.message}{suffix}"
        )


def _format_optional(value: float | None, *, percent: bool = False) -> str:
    if value is None:
        return "n/a"
    if percent:
        return f"{value:.2%}"
    return f"{value:.2f}"


if __name__ == "__main__":
    app()
