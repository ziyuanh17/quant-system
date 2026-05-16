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
    reconcile_market_bars_csv,
    validate_market_bars_csv,
    write_reconciliation_report,
)
from quant.execution import (
    LIVE_TRADING_CONFIRMATION,
    DryRunBrokerAdapter,
    PaperBroker,
    PaperBrokerAdapter,
    evaluate_trading_safety,
    execute_latest_signal,
    execute_latest_signal_dry_run,
    load_paper_broker_state,
    load_trading_safety_config_from_env,
    reconcile_paper_state,
    save_paper_broker_state,
    write_dry_run_order_record,
    write_paper_signal_record,
    write_paper_state_reconciliation_report,
    write_paper_trade_record,
)
from quant.features import (
    build_technical_features,
    load_feature_csv,
    write_feature_artifact,
)
from quant.models.backtest import BacktestConfig, BacktestResult
from quant.models.execution import (
    OrderRequest,
    OrderSide,
    PaperStateReconciliationReport,
    Position,
    TradingMode,
    TradingSafetyConfig,
)
from quant.models.features import TechnicalFeatureConfig
from quant.models.ingestion import IngestRequest
from quant.models.operations import HealthReport, HealthStatus
from quant.models.reconciliation import ProviderReconciliationReport
from quant.models.scheduler import ScheduledTaskResult
from quant.models.validation import ValidationReport
from quant.models.workflow import DataRefreshWorkflowRecord
from quant.operations import (
    build_dashboard_health_status,
    build_health_report,
    write_dashboard_health_status,
)
from quant.scheduler import SchedulerRunner
from quant.strategies import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
    MomentumStrategy,
)
from quant.workflows import WorkflowRunFailed, run_paper_signal_refresh_workflow

app = typer.Typer(no_args_is_help=True)
data_app = typer.Typer(no_args_is_help=True)
features_app = typer.Typer(no_args_is_help=True)
paper_app = typer.Typer(no_args_is_help=True)
schedule_app = typer.Typer(no_args_is_help=True)
ops_app = typer.Typer(no_args_is_help=True)
workflow_app = typer.Typer(no_args_is_help=True)
safety_app = typer.Typer(no_args_is_help=True)
dry_run_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(features_app, name="features")
app.add_typer(paper_app, name="paper")
app.add_typer(schedule_app, name="schedule")
app.add_typer(ops_app, name="ops")
app.add_typer(workflow_app, name="workflow")
app.add_typer(safety_app, name="safety")
app.add_typer(dry_run_app, name="dry-run")


@app.callback()
def main() -> None:
    """Quant research and trading CLI."""


@safety_app.command("check")
def safety_check(
    trading_mode: Annotated[
        TradingMode,
        typer.Option(help="Requested trading mode to evaluate."),
    ] = TradingMode.PAPER,
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live trading."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required phrase for live trading."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for one live order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live mode."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
) -> None:
    """Evaluate fail-closed trading safety gates."""
    if from_env:
        try:
            config = load_trading_safety_config_from_env()
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        config = TradingSafetyConfig(
            mode=trading_mode,
            live_trading_enabled=live_trading_enabled,
            live_trading_confirmation=live_trading_confirmation,
            max_order_notional=max_order_notional,
            broker_name=broker_name,
        )

    check = evaluate_trading_safety(config)
    typer.echo(f"Mode: {check.mode.value}")
    typer.echo(f"Allowed: {check.allowed}")
    if check.issues:
        for issue in check.issues:
            typer.echo(f"- {issue}")
        typer.echo(
            f"Required confirmation: {LIVE_TRADING_CONFIRMATION}"
        )

    if not check.allowed:
        raise typer.Exit(code=1)


@dry_run_app.command("order")
def dry_run_order(
    symbol: Annotated[str, typer.Option(help="Symbol to trade.")] = "AAPL",
    side: Annotated[
        OrderSide,
        typer.Option(help="Order side."),
    ] = OrderSide.BUY,
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity."),
    ] = 1,
    price: Annotated[
        float,
        typer.Option(help="Market price used for the intended order."),
    ] = 100.0,
    broker_name: Annotated[
        str,
        typer.Option(help="Broker name to include in the dry-run record."),
    ] = "dry-run",
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory where dry-run order records are written."),
    ] = Path("data/dry_run/orders"),
) -> None:
    """Record a would-submit market order without placing or filling it."""
    config = TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    check = evaluate_trading_safety(config)
    if not check.allowed:
        raise typer.Exit(code=1)

    adapter = DryRunBrokerAdapter(broker_name=broker_name)
    record = adapter.submit_market_order(
        OrderRequest(symbol=symbol, side=side, quantity=quantity),
        market_price=price,
        safety_check=check,
    )
    record_path = write_dry_run_order_record(record, output_dir)

    typer.echo(f"Dry-run order: {record.id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Broker: {record.broker_name}")
    typer.echo(f"Side: {record.request.side.value}")
    typer.echo(f"Quantity: {record.request.quantity}")
    typer.echo(f"Market price: {record.market_price:,.2f}")
    typer.echo(f"Notional: {record.notional:,.2f}")
    typer.echo(f"Record: {record_path}")


@dry_run_app.command("signal")
def dry_run_signal(
    strategy: Annotated[
        str, typer.Option(help="Strategy name to run.")
    ] = "momentum",
    data: Annotated[
        Path,
        typer.Option(help="CSV file with OHLCV data."),
    ] = Path("data/sample_prices.csv"),
    symbol: Annotated[str, typer.Option(help="Symbol to trade.")] = "AAPL",
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity for actionable signals."),
    ] = 1,
    broker_name: Annotated[
        str,
        typer.Option(help="Broker name to include in dry-run records."),
    ] = "dry-run",
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory where dry-run order records are written."),
    ] = Path("data/dry_run/orders"),
    skip_validation: Annotated[
        bool,
        typer.Option(help="Skip market-data validation before signal runs."),
    ] = False,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
) -> None:
    """Run the latest strategy signal through the dry-run broker path."""
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if not skip_validation:
        _validate_or_exit(data, symbol, min_rows=min_rows)

    config = TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    check = evaluate_trading_safety(config)
    if not check.allowed:
        raise typer.Exit(code=1)

    prices = load_price_csv(data, symbol)
    adapter = DryRunBrokerAdapter(broker_name=broker_name)
    decision, record = execute_latest_signal_dry_run(
        strategy=MomentumStrategy(),
        prices=prices,
        broker=adapter,
        quantity=quantity,
        safety_check=check,
    )

    typer.echo(f"Signal: {decision.action.value}")
    typer.echo(f"Signal date: {decision.signal_date}")
    if record is None:
        typer.echo("Dry-run order: none")
        return

    record_path = write_dry_run_order_record(record, output_dir)
    typer.echo(f"Dry-run order: {record.id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Broker: {record.broker_name}")
    typer.echo(f"Side: {record.request.side.value}")
    typer.echo(f"Quantity: {record.request.quantity}")
    typer.echo(f"Market price: {record.market_price:,.2f}")
    typer.echo(f"Notional: {record.notional:,.2f}")
    typer.echo(f"Record: {record_path}")


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


@data_app.command("reconcile")
def reconcile_data(
    left: Annotated[
        Path,
        typer.Option(help="First normalized market-bars CSV to compare."),
    ],
    right: Annotated[
        Path,
        typer.Option(help="Second normalized market-bars CSV to compare."),
    ],
    symbol: Annotated[str, typer.Option(help="Symbol to reconcile.")] = "AAPL",
    output_dir: Annotated[
        Path,
        typer.Option(
            help="Directory where reconciliation reports are written."
        ),
    ] = Path("data/reconciliation"),
    close_tolerance_pct: Annotated[
        float,
        typer.Option(help="Allowed relative close-price difference."),
    ] = 0.001,
    volume_tolerance_pct: Annotated[
        float,
        typer.Option(help="Allowed relative volume difference."),
    ] = 0.05,
) -> None:
    """Compare two normalized market-bar datasets for one symbol."""
    report = reconcile_market_bars_csv(
        left_path=left,
        right_path=right,
        symbol=symbol,
        close_tolerance_pct=close_tolerance_pct,
        volume_tolerance_pct=volume_tolerance_pct,
    )
    report_path = write_reconciliation_report(
        report, output_dir / f"{symbol}.json"
    )

    _print_reconciliation_report(report)
    typer.echo(f"Report: {report_path}")

    if not report.passed:
        raise typer.Exit(code=1)


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


@paper_app.command("order")
def paper_order(
    symbol: Annotated[str, typer.Option(help="Symbol to trade.")] = "AAPL",
    side: Annotated[
        OrderSide,
        typer.Option(help="Order side."),
    ] = OrderSide.BUY,
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity."),
    ] = 1,
    price: Annotated[
        float,
        typer.Option(help="Market price used for the simulated fill."),
    ] = 100.0,
    initial_cash: Annotated[
        float,
        typer.Option(help="Starting cash for this paper session."),
    ] = 100_000,
    output_dir: Annotated[
        Path,
        typer.Option(help="Directory where paper trade records are written."),
    ] = Path("data/paper/latest"),
) -> None:
    """Submit a single market order to the paper broker."""
    broker = PaperBroker(initial_cash=initial_cash)
    record = broker.submit_market_order(
        OrderRequest(symbol=symbol, side=side, quantity=quantity),
        market_price=price,
    )
    record_path = write_paper_trade_record(record, output_dir)

    typer.echo(f"Order: {record.order.id}")
    typer.echo(f"Status: {record.order.status}")
    if record.order.risk.reason is not None:
        typer.echo(f"Risk reason: {record.order.risk.reason}")
    if record.fill is not None:
        typer.echo(f"Fill price: {record.fill.price:,.2f}")
        typer.echo(f"Fill quantity: {record.fill.quantity}")
    typer.echo(f"Cash: {record.snapshot.cash:,.2f}")
    typer.echo(f"Equity: {record.snapshot.equity:,.2f}")
    typer.echo(f"Record: {record_path}")

    if record.fill is None:
        raise typer.Exit(code=1)


@paper_app.command("reconcile-state")
def paper_reconcile_state(
    state_path: Annotated[
        Path,
        typer.Option(help="Path to the persisted paper broker state."),
    ] = Path("data/paper/state/default.json"),
    signal_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing paper signal JSON records."),
    ] = Path("data/paper/signals"),
    initial_cash: Annotated[
        float,
        typer.Option(help="Cash balance before replaying signal records."),
    ] = 100_000,
    initial_position_quantity: Annotated[
        int,
        typer.Option(help="Optional starting position quantity."),
    ] = 0,
    initial_position_price: Annotated[
        float,
        typer.Option(help="Price basis for the optional starting position."),
    ] = 1.0,
    symbol: Annotated[
        str,
        typer.Option(help="Symbol for the optional starting position."),
    ] = "AAPL",
    cash_tolerance: Annotated[
        float,
        typer.Option(help="Allowed cash and price difference."),
    ] = 0.01,
    output_path: Annotated[
        Path,
        typer.Option(help="Path where the reconciliation report is written."),
    ] = Path("data/paper/reconciliation/state.json"),
) -> None:
    """Reconcile persisted paper state against paper signal audit records."""
    if initial_position_quantity < 0:
        raise typer.BadParameter(
            "initial-position-quantity must be non-negative"
        )
    if initial_position_quantity > 0 and initial_position_price <= 0:
        raise typer.BadParameter("initial-position-price must be positive")
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")
    if not state_path.exists():
        raise typer.BadParameter(f"state path does not exist: {state_path}")

    state = load_paper_broker_state(state_path, default_cash=initial_cash)
    report = reconcile_paper_state(
        state=state,
        state_path=state_path,
        signal_records_dir=signal_records_dir,
        initial_cash=initial_cash,
        initial_positions=_initial_positions(
            symbol=symbol,
            quantity=initial_position_quantity,
            price=initial_position_price,
        ),
        cash_tolerance=cash_tolerance,
    )
    report_path = write_paper_state_reconciliation_report(report, output_path)
    _print_paper_state_reconciliation_report(report, report_path)

    if not report.passed:
        raise typer.Exit(code=1)


@schedule_app.command("paper-order")
def schedule_paper_order(
    symbol: Annotated[str, typer.Option(help="Symbol to trade.")] = "AAPL",
    side: Annotated[
        OrderSide,
        typer.Option(help="Order side."),
    ] = OrderSide.BUY,
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity per scheduled run."),
    ] = 1,
    price: Annotated[
        float,
        typer.Option(help="Market price used for simulated fills."),
    ] = 100.0,
    initial_cash: Annotated[
        float,
        typer.Option(help="Starting cash for the paper broker session."),
    ] = 100_000,
    iterations: Annotated[
        int,
        typer.Option(help="Number of scheduled runs to execute."),
    ] = 1,
    interval_seconds: Annotated[
        float,
        typer.Option(help="Seconds to wait between scheduled runs."),
    ] = 0.0,
    paper_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where paper trade records are written."),
    ] = Path("data/paper/scheduled"),
    run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where scheduler run records are written."),
    ] = Path("data/scheduler/latest"),
) -> None:
    """Run a finite scheduled paper-order loop."""
    if iterations < 1:
        raise typer.BadParameter("iterations must be at least 1")
    if interval_seconds < 0:
        raise typer.BadParameter("interval-seconds must be non-negative")

    broker = PaperBroker(initial_cash=initial_cash)
    runner = SchedulerRunner(output_dir=run_output_dir)
    request = OrderRequest(symbol=symbol, side=side, quantity=quantity)

    def task() -> ScheduledTaskResult:
        record = broker.submit_market_order(request, market_price=price)
        paper_path = write_paper_trade_record(record, paper_output_dir)
        status = record.order.status
        message = f"paper order {status}"
        if record.order.risk.reason is not None:
            message = f"{message}: {record.order.risk.reason}"
        return ScheduledTaskResult(
            message=message,
            artifact_paths=(str(paper_path),),
        )

    records = runner.run_loop(
        task_name="paper-order",
        task=task,
        iterations=iterations,
        interval_seconds=interval_seconds,
    )

    failed_records = [
        record for record in records if record.status.value == "failed"
    ]
    typer.echo(f"Scheduled runs: {len(records)}")
    typer.echo(f"Failures: {len(failed_records)}")
    typer.echo(f"Run records: {run_output_dir}")
    typer.echo(f"Paper records: {paper_output_dir}")

    if failed_records:
        raise typer.Exit(code=1)


@schedule_app.command("paper-signal")
def schedule_paper_signal(
    strategy: Annotated[
        str, typer.Option(help="Strategy name to run.")
    ] = "momentum",
    data: Annotated[
        Path,
        typer.Option(help="CSV file with OHLCV data."),
    ] = Path("data/sample_prices.csv"),
    symbol: Annotated[str, typer.Option(help="Symbol to trade.")] = "AAPL",
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity if the latest signal trades."),
    ] = 1,
    initial_cash: Annotated[
        float,
        typer.Option(help="Starting cash for the paper broker session."),
    ] = 100_000,
    initial_position_quantity: Annotated[
        int,
        typer.Option(help="Optional starting position quantity."),
    ] = 0,
    initial_position_price: Annotated[
        float,
        typer.Option(help="Price basis for the optional starting position."),
    ] = 1.0,
    iterations: Annotated[
        int,
        typer.Option(help="Number of scheduled runs to execute."),
    ] = 1,
    interval_seconds: Annotated[
        float,
        typer.Option(help="Seconds to wait between scheduled runs."),
    ] = 0.0,
    skip_validation: Annotated[
        bool,
        typer.Option(help="Skip market-data validation before signal runs."),
    ] = False,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
    signal_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where paper signal records are written."),
    ] = Path("data/paper/signals"),
    state_path: Annotated[
        Path,
        typer.Option(help="Path for persisted paper broker state."),
    ] = Path("data/paper/state/default.json"),
    run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where scheduler run records are written."),
    ] = Path("data/scheduler/latest"),
) -> None:
    """Run a finite scheduled strategy-to-paper execution loop."""
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if iterations < 1:
        raise typer.BadParameter("iterations must be at least 1")
    if interval_seconds < 0:
        raise typer.BadParameter("interval-seconds must be non-negative")
    if initial_position_quantity < 0:
        raise typer.BadParameter(
            "initial-position-quantity must be non-negative"
        )
    if initial_position_quantity > 0 and initial_position_price <= 0:
        raise typer.BadParameter("initial-position-price must be positive")

    if not skip_validation:
        _validate_or_exit(data, symbol, min_rows=min_rows)

    initial_positions = _initial_positions(
        symbol=symbol,
        quantity=initial_position_quantity,
        price=initial_position_price,
    )
    state = load_paper_broker_state(
        state_path,
        default_cash=initial_cash,
        default_positions=initial_positions,
    )
    broker = PaperBrokerAdapter.from_state(state)
    runner = SchedulerRunner(output_dir=run_output_dir)
    signal_strategy = MomentumStrategy()

    def task() -> ScheduledTaskResult:
        # Reload prices inside each scheduled attempt so future server runs can
        # see data files refreshed by an upstream ingestion task.
        prices = load_price_csv(data, symbol)
        record = execute_latest_signal(
            strategy=signal_strategy,
            prices=prices,
            broker=broker,
            quantity=quantity,
        )
        signal_path = write_paper_signal_record(record, signal_output_dir)
        state_path_written = save_paper_broker_state(
            broker.state(), state_path
        )
        message = f"paper signal {record.decision.action}"
        if record.skipped:
            message = f"{message}: skipped duplicate"
        if record.trade is not None and record.trade.order.risk.reason:
            message = f"{message}: {record.trade.order.risk.reason}"
        return ScheduledTaskResult(
            message=message,
            artifact_paths=(str(signal_path), str(state_path_written)),
        )

    records = runner.run_loop(
        task_name="paper-signal",
        task=task,
        iterations=iterations,
        interval_seconds=interval_seconds,
    )

    failed_records = [
        record for record in records if record.status.value == "failed"
    ]
    typer.echo(f"Scheduled runs: {len(records)}")
    typer.echo(f"Failures: {len(failed_records)}")
    typer.echo(f"Run records: {run_output_dir}")
    typer.echo(f"Signal records: {signal_output_dir}")
    typer.echo(f"State: {state_path}")

    if failed_records:
        raise typer.Exit(code=1)


@workflow_app.command("paper-signal-refresh")
def workflow_paper_signal_refresh(
    symbol: Annotated[
        str,
        typer.Option(help="Symbol to refresh and trade."),
    ] = "AAPL",
    start: Annotated[
        str, typer.Option(help="Inclusive market-data refresh start date.")
    ] = "2024-01-01",
    end: Annotated[
        str | None,
        typer.Option(help="Exclusive market-data refresh end date."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(help="Data provider name."),
    ] = "yfinance",
    strategy: Annotated[
        str, typer.Option(help="Strategy name to run after refresh.")
    ] = "momentum",
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity if the latest signal trades."),
    ] = 1,
    initial_cash: Annotated[
        float, typer.Option(help="Starting cash for the paper broker session.")
    ] = 100_000,
    initial_position_quantity: Annotated[
        int,
        typer.Option(help="Optional starting position quantity."),
    ] = 0,
    initial_position_price: Annotated[
        float,
        typer.Option(help="Price basis for the optional starting position."),
    ] = 1.0,
    iterations: Annotated[
        int,
        typer.Option(help="Number of scheduled paper-signal runs."),
    ] = 1,
    interval_seconds: Annotated[
        float,
        typer.Option(help="Seconds to wait between scheduled runs."),
    ] = 0.0,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum row count required by validation."),
    ] = 1,
    raw_dir: Annotated[
        Path,
        typer.Option(help="Root directory for refreshed raw data."),
    ] = Path("data/raw"),
    normalized_dir: Annotated[
        Path,
        typer.Option(help="Root directory for refreshed normalized data."),
    ] = Path("data/normalized"),
    validation_dir: Annotated[
        Path,
        typer.Option(help="Root directory for validation report artifacts."),
    ] = Path("data/validation"),
    metadata_dir: Annotated[
        Path,
        typer.Option(help="Root directory for dataset metadata artifacts."),
    ] = Path("data/metadata"),
    workflow_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where workflow records are written."),
    ] = Path("data/workflows/paper-signal-refresh"),
    signal_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where paper signal records are written."),
    ] = Path("data/paper/signals"),
    state_path: Annotated[
        Path,
        typer.Option(help="Path for persisted paper broker state."),
    ] = Path("data/paper/state/default.json"),
    run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where scheduler run records are written."),
    ] = Path("data/scheduler/latest"),
    lock_path: Annotated[
        Path,
        typer.Option(help="Lock file that prevents overlapping workflow runs."),
    ] = Path("data/locks/paper-signal-refresh.lock"),
    lock_stale_after_seconds: Annotated[
        int,
        typer.Option(help="Seconds before an existing workflow lock is stale."),
    ] = 7200,
) -> None:
    """Refresh data, validate it, then run the paper-signal scheduler."""
    _validate_paper_signal_options(
        strategy=strategy,
        iterations=iterations,
        interval_seconds=interval_seconds,
        initial_position_quantity=initial_position_quantity,
        initial_position_price=initial_position_price,
    )
    if provider != "yfinance":
        raise typer.BadParameter("Only yfinance is implemented right now.")

    try:
        record = run_paper_signal_refresh_workflow(
            provider=YFinanceMarketBarProvider(),
            symbol=symbol,
            start=start,
            end=end,
            raw_dir=raw_dir,
            normalized_dir=normalized_dir,
            validation_dir=validation_dir,
            metadata_dir=metadata_dir,
            workflow_output_dir=workflow_output_dir,
            strategy=strategy,
            quantity=quantity,
            initial_cash=initial_cash,
            initial_position_quantity=initial_position_quantity,
            initial_position_price=initial_position_price,
            iterations=iterations,
            interval_seconds=interval_seconds,
            min_rows=min_rows,
            signal_output_dir=signal_output_dir,
            state_path=state_path,
            run_output_dir=run_output_dir,
            lock_path=lock_path,
            lock_stale_after_seconds=lock_stale_after_seconds,
        )
    except WorkflowRunFailed as exc:
        _print_workflow_record(exc.record, workflow_output_dir)
        raise typer.Exit(code=1) from exc

    _print_workflow_record(record, workflow_output_dir)


@ops_app.command("health")
def ops_health(
    run_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing scheduler run JSON records."),
    ] = Path("data/scheduler/latest"),
    signal_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing paper signal JSON records."),
    ] = Path("data/paper/signals"),
    state_path: Annotated[
        Path,
        typer.Option(help="Path to the persisted paper broker state file."),
    ] = Path("data/paper/state/default.json"),
    logs_dir: Annotated[
        Path,
        typer.Option(help="Directory containing service wrapper logs."),
    ] = Path("logs"),
    lock_path: Annotated[
        Path | None,
        typer.Option(help="Optional workflow lock file to inspect."),
    ] = Path("data/locks/paper-signal-refresh.lock"),
    lock_stale_after_seconds: Annotated[
        int,
        typer.Option(help="Seconds before a workflow lock is stale."),
    ] = 7200,
    reconcile_state: Annotated[
        bool,
        typer.Option(help="Reconcile paper state against signal records."),
    ] = False,
    initial_cash: Annotated[
        float,
        typer.Option(help="Cash balance before replaying signal records."),
    ] = 100_000,
    cash_tolerance: Annotated[
        float,
        typer.Option(help="Allowed cash and price difference."),
    ] = 0.01,
    reconciliation_report_path: Annotated[
        Path,
        typer.Option(
            help="Path where reconciliation health report is written."
        ),
    ] = Path("data/paper/reconciliation/health-state.json"),
) -> None:
    """Check local service health from durable artifacts."""
    if lock_stale_after_seconds <= 0:
        raise typer.BadParameter("lock-stale-after-seconds must be positive")
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")

    report = build_health_report(
        run_records_dir=run_records_dir,
        signal_records_dir=signal_records_dir,
        state_path=state_path,
        logs_dir=logs_dir,
        lock_path=lock_path,
        lock_stale_after_seconds=lock_stale_after_seconds,
        reconcile_state=reconcile_state,
        initial_cash=initial_cash,
        cash_tolerance=cash_tolerance,
        reconciliation_report_path=(
            reconciliation_report_path if reconcile_state else None
        ),
    )
    _print_health_report(report)

    if report.status == HealthStatus.FAILED:
        raise typer.Exit(code=1)


@ops_app.command("publish-status")
def ops_publish_status(
    output_path: Annotated[
        Path,
        typer.Option(help="Dashboard status JSON path."),
    ] = Path("site/status.json"),
    run_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing scheduler run JSON records."),
    ] = Path("data/scheduler/latest"),
    signal_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing paper signal JSON records."),
    ] = Path("data/paper/signals"),
    state_path: Annotated[
        Path,
        typer.Option(help="Path to the persisted paper broker state file."),
    ] = Path("data/paper/state/default.json"),
    logs_dir: Annotated[
        Path,
        typer.Option(help="Directory containing service wrapper logs."),
    ] = Path("logs"),
    lock_path: Annotated[
        Path | None,
        typer.Option(help="Optional workflow lock file to inspect."),
    ] = Path("data/locks/paper-signal-refresh.lock"),
    lock_stale_after_seconds: Annotated[
        int,
        typer.Option(help="Seconds before a workflow lock is stale."),
    ] = 7200,
    reconcile_state: Annotated[
        bool,
        typer.Option(help="Reconcile paper state against signal records."),
    ] = True,
    initial_cash: Annotated[
        float,
        typer.Option(help="Cash balance before replaying signal records."),
    ] = 100_000,
    cash_tolerance: Annotated[
        float,
        typer.Option(help="Allowed cash and price difference."),
    ] = 0.01,
    fail_on_failed: Annotated[
        bool,
        typer.Option(help="Exit nonzero after writing failed status."),
    ] = False,
) -> None:
    """Publish a sanitized health snapshot for the static dashboard."""
    if lock_stale_after_seconds <= 0:
        raise typer.BadParameter("lock-stale-after-seconds must be positive")
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")

    report = build_health_report(
        run_records_dir=run_records_dir,
        signal_records_dir=signal_records_dir,
        state_path=state_path,
        logs_dir=logs_dir,
        lock_path=lock_path,
        lock_stale_after_seconds=lock_stale_after_seconds,
        reconcile_state=reconcile_state,
        initial_cash=initial_cash,
        cash_tolerance=cash_tolerance,
        reconciliation_report_path=None,
    )
    status = build_dashboard_health_status(report)
    path = write_dashboard_health_status(status, output_path)
    typer.echo(f"Status: {status.status.value}")
    typer.echo(f"Issues: {status.issue_count}")
    typer.echo(f"Dashboard status: {path}")

    # Publishing should normally succeed even for failed health, because a
    # visible red dashboard is more useful than leaving yesterday's status live.
    if fail_on_failed and status.status == HealthStatus.FAILED:
        raise typer.Exit(code=1)


def _validate_paper_signal_options(
    *,
    strategy: str,
    iterations: int,
    interval_seconds: float,
    initial_position_quantity: int,
    initial_position_price: float,
) -> None:
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if iterations < 1:
        raise typer.BadParameter("iterations must be at least 1")
    if interval_seconds < 0:
        raise typer.BadParameter("interval-seconds must be non-negative")
    if initial_position_quantity < 0:
        raise typer.BadParameter(
            "initial-position-quantity must be non-negative"
        )
    if initial_position_quantity > 0 and initial_position_price <= 0:
        raise typer.BadParameter("initial-position-price must be positive")


def _initial_positions(
    *,
    symbol: str,
    quantity: int,
    price: float,
) -> tuple[Position, ...]:
    if quantity == 0:
        return ()
    return (
        Position(
            symbol=symbol,
            quantity=quantity,
            average_price=price,
            last_price=price,
        ),
    )


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


def _print_health_report(report: HealthReport) -> None:
    typer.echo(f"Status: {report.status.value}")
    typer.echo(
        "Latest run: "
        f"{_format_health_value(report.latest_run_status)} "
        f"at {_format_health_value(report.latest_run_completed_at)} "
        f"({_format_health_value(report.latest_run_path)})"
    )
    typer.echo(
        "Latest signal: "
        f"action={_format_health_value(report.latest_signal_action)} "
        f"date={_format_health_value(report.latest_signal_date)} "
        f"skipped={_format_health_value(report.latest_signal_skipped)} "
        f"({_format_health_value(report.latest_signal_path)})"
    )
    typer.echo(
        "State: "
        f"cash={_format_health_value(report.state_cash)} "
        f"positions={_format_health_value(report.state_position_count)} "
        f"({report.state_path})"
    )
    typer.echo(f"Logs: {report.logs_dir} ({report.log_count} files)")
    typer.echo(
        "Lock: "
        f"status={report.lock_status} "
        f"owner={_format_health_value(report.lock_owner)} "
        f"expires_at={_format_health_value(report.lock_expires_at)} "
        f"({_format_health_value(report.lock_path)})"
    )
    typer.echo(
        "Reconciliation: "
        f"status={report.reconciliation_status} "
        "differences="
        f"{_format_health_value(report.reconciliation_difference_count)} "
        f"({_format_health_value(report.reconciliation_report_path)})"
    )
    typer.echo(f"Issues: {report.issue_count}")

    for issue in report.issues:
        typer.echo(
            f"[{issue.severity.value}] {issue.code}: {issue.message}"
        )


def _print_paper_state_reconciliation_report(
    report: PaperStateReconciliationReport,
    report_path: Path,
) -> None:
    status = "passed" if report.passed else "failed"
    typer.echo(f"Status: {status}")
    typer.echo(f"State: {report.state_path}")
    typer.echo(f"Signal records: {report.signal_records_dir}")
    typer.echo(f"Signal record count: {report.signal_record_count}")
    typer.echo(f"Filled trades: {report.filled_trade_count}")
    typer.echo(f"Expected cash: {report.expected_cash:,.2f}")
    typer.echo(f"Actual cash: {report.actual_cash:,.2f}")
    typer.echo(f"Differences: {report.difference_count}")
    for difference in report.differences:
        typer.echo(
            f"[difference] {difference.field}: {difference.message} "
            f"(expected={difference.expected}, actual={difference.actual})"
        )
    typer.echo(f"Report: {report_path}")


def _print_workflow_record(
    record: DataRefreshWorkflowRecord,
    output_dir: Path,
) -> None:
    record_path = output_dir / f"{record.workflow_id}.json"
    typer.echo(f"Workflow: {record.workflow_name}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Message: {record.message}")
    typer.echo(f"Symbol: {record.symbol}")
    typer.echo(f"Provider: {record.provider}")
    typer.echo(f"Normalized: {_format_health_value(record.normalized_path)}")
    typer.echo(
        "Validation report: "
        f"{_format_health_value(record.validation_report_path)}"
    )
    typer.echo(f"Lock: {_format_health_value(record.lock_path)}")
    typer.echo(f"Scheduler runs: {len(record.scheduler_run_paths)}")
    typer.echo(f"Record: {record_path}")


def _format_health_value(value: object | None) -> str:
    if value is None:
        return "n/a"
    return str(value)


def _print_reconciliation_report(
    report: ProviderReconciliationReport,
) -> None:
    status = "passed" if report.passed else "failed"
    typer.echo(f"Left: {report.left_dataset}")
    typer.echo(f"Right: {report.right_dataset}")
    typer.echo(f"Symbol: {report.symbol}")
    typer.echo(f"Rows: left={report.left_rows}, right={report.right_rows}")
    typer.echo(f"Overlap rows: {report.overlap_rows}")
    typer.echo(f"Status: {status}")
    typer.echo(f"Issues: {report.issue_count}")
    typer.echo(f"Close differences: {len(report.close_differences)}")
    typer.echo(f"Volume differences: {len(report.volume_differences)}")

    for issue in report.issues:
        suffix = f" ({issue.field})" if issue.field is not None else ""
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
