from pathlib import Path
from typing import Annotated

import pandas as pd
import typer

from quant.backtest import VectorBTBacktester
from quant.backtest.artifacts import write_backtest_artifacts
from quant.data import (
    YFinanceMarketBarProvider,
    ingest_market_bars,
    load_price_csv,
    validate_market_bars_csv,
)
from quant.features import (
    build_technical_features,
    load_feature_csv,
    write_feature_artifact,
)
from quant.models.backtest import BacktestConfig, BacktestResult
from quant.models.features import TechnicalFeatureConfig
from quant.models.ingestion import IngestRequest
from quant.models.validation import ValidationReport
from quant.strategies import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
    MomentumStrategy,
)

app = typer.Typer(no_args_is_help=True)
data_app = typer.Typer(no_args_is_help=True)
features_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(features_app, name="features")


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
    features_data: Annotated[
        Path | None,
        typer.Option(help="Feature CSV for feature-based strategies."),
    ] = None,
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
    skip_validation: Annotated[
        bool,
        typer.Option(help="Skip market-data validation before backtesting."),
    ] = False,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
    fast_feature: Annotated[
        str,
        typer.Option(help="Fast feature column for feature-momentum."),
    ] = "ma_5",
    slow_feature: Annotated[
        str,
        typer.Option(help="Slow feature column for feature-momentum."),
    ] = "ma_20",
) -> None:
    """Run a VectorBT-backed signal backtest."""
    if strategy == "momentum":
        result, trades = _run_price_backtest(
            data=data,
            symbol=symbol,
            initial_cash=initial_cash,
            fees=fees,
            skip_validation=skip_validation,
            min_rows=min_rows,
        )
    elif strategy == "feature-momentum":
        result, trades = _run_feature_backtest(
            features_data=features_data,
            symbol=symbol,
            initial_cash=initial_cash,
            fees=fees,
            fast_feature=fast_feature,
            slow_feature=slow_feature,
        )
    else:
        raise typer.BadParameter(
            "Supported strategies are: momentum, feature-momentum."
        )

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


def _run_price_backtest(
    *,
    data: Path,
    symbol: str,
    initial_cash: float,
    fees: float,
    skip_validation: bool,
    min_rows: int,
) -> tuple[BacktestResult, pd.DataFrame]:
    if not skip_validation:
        _validate_or_exit(data, symbol, min_rows=min_rows)

    prices = load_price_csv(data, symbol)
    return VectorBTBacktester(
        BacktestConfig(initial_cash=initial_cash, fees=fees)
    ).run_with_trades(MomentumStrategy(), prices)


def _run_feature_backtest(
    *,
    features_data: Path | None,
    symbol: str,
    initial_cash: float,
    fees: float,
    fast_feature: str,
    slow_feature: str,
) -> tuple[BacktestResult, pd.DataFrame]:
    if features_data is None:
        raise typer.BadParameter(
            "--features-data is required for feature-momentum."
        )

    # FeatureData validates artifact shape, but market-bar validation is not
    # applicable because feature CSVs intentionally lack OHLCV columns.
    features = load_feature_csv(features_data, symbol)
    strategy = FeatureMomentumStrategy(
        FeatureMomentumConfig(
            fast_column=fast_feature,
            slow_column=slow_feature,
        )
    )
    return VectorBTBacktester(
        BacktestConfig(initial_cash=initial_cash, fees=fees)
    ).run_feature_with_trades(strategy, features)


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
    validation_dir: Annotated[
        Path,
        typer.Option(help="Root directory for validation report artifacts."),
    ] = Path("data/validation"),
    metadata_dir: Annotated[
        Path,
        typer.Option(help="Root directory for dataset metadata artifacts."),
    ] = Path("data/metadata"),
    skip_validation: Annotated[
        bool,
        typer.Option(help="Skip validation after writing normalized data."),
    ] = False,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
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
        validation_root=validation_dir,
        metadata_root=metadata_dir,
        validate=not skip_validation,
        min_rows=min_rows,
    )

    validation_failed = False
    for artifact in artifacts:
        typer.echo(f"Raw: {artifact.raw_path}")
        typer.echo(f"Normalized: {artifact.normalized_path}")
        if artifact.validation_report_path is not None:
            typer.echo(f"Validation report: {artifact.validation_report_path}")
        if artifact.metadata_path is not None:
            typer.echo(f"Metadata: {artifact.metadata_path}")
        if artifact.validation_passed is False:
            validation_failed = True

    if validation_failed:
        raise typer.Exit(code=1)


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
    report = _validate_or_exit(data, symbol, min_rows=min_rows)
    _print_validation_report(report)


@features_app.command("build")
def build_features(
    data: Annotated[
        Path,
        typer.Option(help="Normalized market-bars CSV to build features from."),
    ],
    symbol: Annotated[
        str, typer.Option(help="Symbol to build features for.")
    ] = "AAPL",
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory where feature artifacts are written."),
    ] = Path("data/features/technical"),
    fast_window: Annotated[
        int, typer.Option(help="Fast moving-average window.")
    ] = 5,
    slow_window: Annotated[
        int, typer.Option(help="Slow moving-average window.")
    ] = 20,
    volatility_window: Annotated[
        int, typer.Option(help="Rolling volatility window.")
    ] = 20,
    momentum_window: Annotated[
        int, typer.Option(help="Momentum percent-change window.")
    ] = 20,
    skip_validation: Annotated[
        bool,
        typer.Option(
            help="Skip market-data validation before feature building."
        ),
    ] = False,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
) -> None:
    """Build technical features from normalized market bars."""
    # Features are downstream of data quality, so validation is on by default.
    if not skip_validation:
        _validate_or_exit(data, symbol, min_rows=min_rows)

    prices = load_price_csv(data, symbol)
    features = build_technical_features(
        prices,
        TechnicalFeatureConfig(
            fast_window=fast_window,
            slow_window=slow_window,
            volatility_window=volatility_window,
            momentum_window=momentum_window,
        ),
    )
    artifact = write_feature_artifact(features, output_dir, symbol)
    typer.echo(f"Features: {artifact.features_path}")


def _validate_or_exit(
    data: Path,
    symbol: str,
    *,
    min_rows: int,
) -> ValidationReport:
    report = validate_market_bars_csv(data, symbol, min_rows=min_rows)
    if not report.passed:
        _print_validation_report(report)
        raise typer.Exit(code=1)
    return report


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
