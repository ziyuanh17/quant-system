"""Command-line interface for quant-system operations and research workflows."""

import os
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Annotated
from zoneinfo import ZoneInfo

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
    ALPACA_PAPER_REHEARSAL_CONFIRMATION,
    LIVE_TRADING_CONFIRMATION,
    AlpacaPaperBrokerClient,
    AlpacaPaperConfig,
    DryRunBrokerAdapter,
    FakeLiveBrokerClient,
    LiveBrokerAdapter,
    LiveRehearsalBlockedError,
    PaperBroker,
    PaperBrokerAdapter,
    compare_paper_signal_to_dry_run_order,
    evaluate_trading_safety,
    execute_latest_signal,
    execute_latest_signal_dry_run,
    latest_json,
    load_live_order_records,
    load_paper_broker_state,
    load_trading_safety_config_from_env,
    reconcile_live_state,
    reconcile_paper_state,
    run_alpaca_paper_order_rehearsal,
    save_paper_broker_state,
    write_dry_run_order_record,
    write_live_account_snapshot,
    write_live_reconciliation_report,
    write_paper_dry_run_comparison_report,
    write_paper_signal_record,
    write_paper_state_reconciliation_report,
    write_paper_trade_record,
)
from quant.features import (
    build_technical_features,
    load_feature_csv,
    write_feature_artifact,
)
from quant.models.autonomous import (
    AutonomousDryRunStatus,
    SupervisedDryRunServiceStatus,
)
from quant.models.backtest import BacktestConfig, BacktestResult
from quant.models.execution import (
    OrderRequest,
    OrderSide,
    PaperStateReconciliationReport,
    Position,
    TradingMode,
    TradingSafetyCheck,
    TradingSafetyConfig,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionPlanStatus,
)
from quant.models.features import TechnicalFeatureConfig
from quant.models.ingestion import IngestRequest
from quant.models.operations import HealthReport, HealthStatus
from quant.models.operator import (
    FiniteSupervisedProviderStatus,
    SupervisedProviderDiscoveryLoopStatus,
    SupervisedProviderDiscoveryStatus,
)
from quant.models.reconciliation import ProviderReconciliationReport
from quant.models.scheduler import ScheduledTaskResult
from quant.models.validation import ValidationReport
from quant.models.workflow import (
    DataRefreshWorkflowRecord,
    SemanticTargetWorkflowStatus,
)
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
from quant.workflows import (
    WorkflowRunFailed,
    inspect_activated_dry_run_operator_request,
    inspect_activated_semantic_paper_operator_request,
    load_and_verify_semantic_target_alpaca_paper_rehearsal,
    prepare_momentum_semantic_paper_request,
    prepare_semantic_target_alpaca_paper_request,
    run_activated_dry_run_operator_request,
    run_activated_semantic_paper_operator_request,
    run_alpaca_paper_refresh_workflow,
    run_dry_run_refresh_workflow,
    run_finite_autonomous_dry_run_loop,
    run_finite_supervised_provider_loop,
    run_paper_signal_refresh_workflow,
    run_semantic_target_alpaca_paper_fake_rehearsal,
    run_semantic_target_alpaca_paper_operator_request,
    run_supervised_provider_discovery_loop_operator_request,
    run_supervised_provider_discovery_operator_request,
    run_supervised_provider_operator_request,
)

app = typer.Typer(no_args_is_help=True)
data_app = typer.Typer(no_args_is_help=True)
features_app = typer.Typer(no_args_is_help=True)
paper_app = typer.Typer(no_args_is_help=True)
schedule_app = typer.Typer(no_args_is_help=True)
ops_app = typer.Typer(no_args_is_help=True)
workflow_app = typer.Typer(no_args_is_help=True)
safety_app = typer.Typer(no_args_is_help=True)
dry_run_app = typer.Typer(no_args_is_help=True)
live_app = typer.Typer(no_args_is_help=True)
web_app = typer.Typer(no_args_is_help=True)
semantic_paper_app = typer.Typer(no_args_is_help=True)
semantic_target_app = typer.Typer(no_args_is_help=True)
app.add_typer(data_app, name="data")
app.add_typer(features_app, name="features")
app.add_typer(paper_app, name="paper")
app.add_typer(schedule_app, name="schedule")
app.add_typer(ops_app, name="ops")
app.add_typer(workflow_app, name="workflow")
app.add_typer(safety_app, name="safety")
app.add_typer(dry_run_app, name="dry-run")
app.add_typer(live_app, name="live")
app.add_typer(web_app, name="web")
app.add_typer(semantic_paper_app, name="semantic-paper")
app.add_typer(semantic_target_app, name="semantic-target")


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


@dry_run_app.command("compare-paper")
def dry_run_compare_paper(
    paper_signal_path: Annotated[
        Path | None,
        typer.Option(help="Paper signal record to compare."),
    ] = None,
    dry_run_order_path: Annotated[
        Path | None,
        typer.Option(help="Dry-run order record to compare."),
    ] = None,
    paper_signal_dir: Annotated[
        Path,
        typer.Option(help="Directory containing paper signal records."),
    ] = Path("data/paper/signals"),
    dry_run_order_dir: Annotated[
        Path,
        typer.Option(help="Directory containing dry-run order records."),
    ] = Path("data/dry_run/orders"),
    output_path: Annotated[
        Path,
        typer.Option(help="Path where the comparison report is written."),
    ] = Path("data/dry_run/comparison/latest.json"),
    tolerance: Annotated[
        float,
        typer.Option(help="Allowed market price difference."),
    ] = 0.01,
) -> None:
    """Compare paper signal intent with dry-run broker intent."""
    if tolerance < 0:
        raise typer.BadParameter("tolerance must be non-negative")

    resolved_paper_signal_path = paper_signal_path or latest_json(
        paper_signal_dir
    )
    if resolved_paper_signal_path is None:
        raise typer.BadParameter(
            f"No paper signal records found in {paper_signal_dir}"
        )
    resolved_dry_run_order_path = dry_run_order_path or latest_json(
        dry_run_order_dir
    )
    report = compare_paper_signal_to_dry_run_order(
        paper_signal_path=resolved_paper_signal_path,
        dry_run_order_path=resolved_dry_run_order_path,
        tolerance=tolerance,
    )
    report_path = write_paper_dry_run_comparison_report(report, output_path)

    typer.echo(f"Status: {report.status.value}")
    typer.echo(f"Differences: {report.difference_count}")
    for difference in report.differences:
        typer.echo(
            f"[{difference.field}] paper={difference.paper_value} "
            f"dry_run={difference.dry_run_value}: {difference.message}"
        )
    typer.echo(f"Report: {report_path}")

    if not report.passed:
        raise typer.Exit(code=1)


@dry_run_app.command("activated-target")
def dry_run_activated_target(
    request_path: Annotated[
        Path,
        typer.Option(help="Reviewed activated dry-run request artifact."),
    ],
    activation_root: Annotated[
        Path,
        typer.Option(help="Directory for activation evidence."),
    ] = Path("data/semantic-target/activation"),
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for dry-run orchestration evidence."),
    ] = Path("data/semantic-target/dry-run"),
) -> None:
    """Run one reviewed activated semantic-target dry-run request."""
    try:
        result = run_activated_dry_run_operator_request(
            request_path=request_path,
            activation_root=activation_root,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    activated = result.activated_workflow
    typer.echo(f"Request: {result.request_artifact_path}")
    typer.echo(
        f"Activation decision: {activated.activation_evaluation.decision.value}"
    )
    typer.echo(
        f"Activation consumption: "
        f"{activated.activation_consumption.consumption_id}"
    )
    if activated.workflow is None:
        typer.echo(f"Blocked: {activated.activation_consumption.reason}")
        raise typer.Exit(code=1)

    record = activated.workflow.record
    typer.echo(f"Orchestration: {record.orchestration_id}")
    typer.echo(f"Workflow status: {record.status.value}")
    typer.echo(
        "Dry-run status: "
        f"{record.dry_run_status.value if record.dry_run_status else 'none'}"
    )
    record_path = (
        output_root / "orchestrations" / f"{record.orchestration_id}.json"
    )
    typer.echo(f"Record: {record_path}")
    if (
        record.status != SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
        or record.dry_run_status == ExecutionDryRunStatus.BLOCKED
    ):
        raise typer.Exit(code=1)


@dry_run_app.command("inspect-activated-target")
def dry_run_inspect_activated_target(
    request_path: Annotated[
        Path,
        typer.Option(help="Activated dry-run request to inspect."),
    ],
) -> None:
    """Explain and validate a request without creating or consuming evidence."""
    try:
        inspection = inspect_activated_dry_run_operator_request(request_path)
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {inspection.request_id}")
    typer.echo(f"Valid now: {'yes' if inspection.valid_now else 'no'}")
    typer.echo(f"Summary: {inspection.summary}")
    if inspection.symbol is not None:
        typer.echo(f"Symbol: {inspection.symbol}")
    if inspection.current_quantity is not None:
        typer.echo(f"Current position: {inspection.current_quantity} shares")
    if inspection.approved_target_quantity is not None:
        typer.echo(
            f"Approved target: {inspection.approved_target_quantity} shares"
        )
    if inspection.intended_order_side is None:
        typer.echo("Intended order: none")
    else:
        typer.echo(
            "Intended order: "
            f"{inspection.intended_order_side.value.upper()} "
            f"{inspection.intended_order_quantity} shares at reference price "
            f"${inspection.reference_price:.2f} "
            f"(${inspection.intended_order_notional:.2f} notional)"
        )
    typer.echo(
        f"Authorization valid until: {inspection.authorization_valid_until}"
    )
    typer.echo(
        "Base rehearsal passed: "
        f"{'yes' if inspection.base_rehearsal_passed else 'no'}"
    )
    typer.echo(
        "Activation-consumption rehearsal passed: "
        + (
            "yes"
            if inspection.activation_consumption_rehearsal_passed
            else "no"
        )
    )
    for issue in inspection.issues:
        typer.echo(f"Blocked because: {issue}")
    typer.echo("Inspection created no activation or execution artifacts.")
    if not inspection.valid_now:
        raise typer.Exit(code=1)


@semantic_paper_app.command("activated-target")
def semantic_paper_activated_target(
    request_path: Annotated[
        Path,
        typer.Option(help="Reviewed activated local semantic-paper request."),
    ],
    activation_root: Annotated[
        Path,
        typer.Option(help="Directory for activation evidence."),
    ] = Path("data/semantic-target/activation"),
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for local semantic-paper evidence."),
    ] = Path("data/semantic-target/local-paper"),
) -> None:
    """Run one reviewed activated target through local semantic paper."""
    try:
        result = run_activated_semantic_paper_operator_request(
            request_path=request_path,
            activation_root=activation_root,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    activated = result.activated_workflow
    typer.echo(f"Request: {result.request_artifact_path}")
    typer.echo(
        f"Activation decision: {activated.activation_evaluation.decision.value}"
    )
    typer.echo(
        f"Activation consumption: "
        f"{activated.activation_consumption.consumption_id}"
    )
    if activated.workflow is None:
        typer.echo(f"Blocked: {activated.activation_consumption.reason}")
        raise typer.Exit(code=1)

    record = activated.workflow.record
    typer.echo(f"Orchestration: {record.orchestration_id}")
    typer.echo(f"Workflow status: {record.status.value}")
    execution_status = (
        record.execution_status.value if record.execution_status else "none"
    )
    typer.echo(f"Execution status: {execution_status}")
    typer.echo(
        "Reconciliation: "
        f"{record.reconciliation_report_id or 'none'}"
    )
    record_path = (
        output_root / "orchestrations" / f"{record.orchestration_id}.json"
    )
    typer.echo(f"Record: {record_path}")
    if (
        record.status != SemanticTargetWorkflowStatus.EXECUTION_COMPLETED
        or record.execution_status != ExecutionPlanStatus.SATISFIED
    ):
        raise typer.Exit(code=1)


@semantic_paper_app.command("prepare-momentum-request")
def semantic_paper_prepare_momentum_request(
    request_id: Annotated[
        str,
        typer.Option(help="Safe ID for the generated request."),
    ],
    data: Annotated[
        Path,
        typer.Option(help="CSV file with OHLCV market bars."),
    ] = Path("data/sample_prices.csv"),
    symbol: Annotated[str, typer.Option(help="Symbol to evaluate.")] = "AAPL",
    quantity: Annotated[
        int,
        typer.Option(help="Long target shares for a buy signal."),
    ] = 1,
    current_position: Annotated[
        int,
        typer.Option(help="Initial local-paper position in shares."),
    ] = 0,
    current_average_price: Annotated[
        float | None,
        typer.Option(help="Average price for the initial position."),
    ] = None,
    initial_cash: Annotated[
        float,
        typer.Option(help="Initial local-paper cash balance."),
    ] = 100_000,
    fast_window: Annotated[
        int,
        typer.Option(help="Legacy momentum fast moving-average window."),
    ] = 5,
    slow_window: Annotated[
        int,
        typer.Option(help="Legacy momentum slow moving-average window."),
    ] = 20,
    min_rows: Annotated[
        int,
        typer.Option(help="Minimum market-bar rows required."),
    ] = 1,
    max_absolute_target: Annotated[
        float,
        typer.Option(help="Risk-policy max absolute approved target."),
    ] = 100,
    valid_for_seconds: Annotated[
        int,
        typer.Option(help="How long generated activation stays valid."),
    ] = 3600,
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for generated request inputs."),
    ] = Path("data/semantic-target/local-paper-requests"),
) -> None:
    """Prepare a reviewed local-paper request from legacy momentum."""
    try:
        bundle = prepare_momentum_semantic_paper_request(
            request_id=request_id,
            data_path=data,
            symbol=symbol,
            quantity=quantity,
            current_position=current_position,
            current_average_price=current_average_price,
            initial_cash=initial_cash,
            fast_window=fast_window,
            slow_window=slow_window,
            min_rows=min_rows,
            max_absolute_target=Decimal(str(max_absolute_target)),
            valid_for_seconds=valid_for_seconds,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {bundle.request_path}")
    typer.echo(f"Signal: {bundle.signal_action.value}")
    typer.echo(f"Signal date: {bundle.signal_date}")
    typer.echo(f"Reference price: {bundle.reference_price:,.2f}")
    typer.echo(f"Target quantity: {bundle.target_quantity}")
    typer.echo(
        f"Activation rehearsal: {bundle.activation_rehearsal_report_path}"
    )
    typer.echo(f"Authorization: {bundle.authorization_path}")


@semantic_paper_app.command("inspect-activated-target")
def semantic_paper_inspect_activated_target(
    request_path: Annotated[
        Path,
        typer.Option(help="Activated local semantic-paper request to inspect."),
    ],
) -> None:
    """Explain and validate a local semantic-paper request without writing."""
    try:
        inspection = inspect_activated_semantic_paper_operator_request(
            request_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {inspection.request_id}")
    typer.echo(f"Valid now: {'yes' if inspection.valid_now else 'no'}")
    typer.echo(f"Summary: {inspection.summary}")
    if inspection.symbol is not None:
        typer.echo(f"Symbol: {inspection.symbol}")
    if inspection.current_quantity is not None:
        typer.echo(f"Current position: {inspection.current_quantity} shares")
    if inspection.approved_target_quantity is not None:
        typer.echo(
            f"Approved target: {inspection.approved_target_quantity} shares"
        )
    if inspection.intended_order_side is None:
        typer.echo("Intended order: none")
    else:
        typer.echo(
            "Intended order: "
            f"{inspection.intended_order_side.value.upper()} "
            f"{inspection.intended_order_quantity} shares at reference price "
            f"${inspection.reference_price:.2f} "
            f"(${inspection.intended_order_notional:.2f} notional)"
        )
    typer.echo(f"Initial cash: {inspection.initial_cash:,.2f}")
    typer.echo(
        f"Authorization valid until: {inspection.authorization_valid_until}"
    )
    typer.echo(
        "Base rehearsal passed: "
        f"{'yes' if inspection.base_rehearsal_passed else 'no'}"
    )
    typer.echo(
        "Activation-consumption rehearsal passed: "
        + (
            "yes"
            if inspection.activation_consumption_rehearsal_passed
            else "no"
        )
    )
    for issue in inspection.issues:
        typer.echo(f"Blocked because: {issue}")
    typer.echo("Inspection created no activation or execution artifacts.")
    if not inspection.valid_now:
        raise typer.Exit(code=1)


@semantic_target_app.command("alpaca-paper-fake-rehearsal")
def semantic_target_alpaca_paper_fake_rehearsal(
    rehearsal_id: Annotated[
        str,
        typer.Option(help="Safe ID for the fake Alpaca paper rehearsal."),
    ] = "semantic-target-alpaca-paper-fake",
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for fake-client rehearsal evidence."),
    ] = Path("data/semantic-target/alpaca-paper-fake-rehearsal"),
) -> None:
    """Run one fake-client semantic-target Alpaca paper rehearsal."""
    try:
        run_semantic_target_alpaca_paper_fake_rehearsal(
            rehearsal_id=rehearsal_id,
            output_root=output_root,
            evaluated_at=datetime.now(UTC),
        )
        report_path = output_root / "reports" / f"{rehearsal_id}.json"
        verified = load_and_verify_semantic_target_alpaca_paper_rehearsal(
            report_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Report: {report_path}")
    typer.echo(f"Passed: {'yes' if verified.passed else 'no'}")
    typer.echo(f"First status: {verified.first_status.value}")
    typer.echo(f"Second status: {verified.second_status.value}")
    typer.echo(f"Execution plan: {verified.execution_plan_id}")
    typer.echo(f"Orders: {verified.order_count}")
    typer.echo(f"Fills: {verified.fill_count}")
    typer.echo(f"Final position: {verified.final_position_quantity}")
    typer.echo(f"Reconciliations: {verified.reconciliation_report_count}")
    typer.echo(f"Evidence files: {len(verified.evidence_paths)}")
    if not verified.passed:
        raise typer.Exit(code=1)


@semantic_target_app.command("alpaca-paper")
def semantic_target_alpaca_paper(
    request_path: Annotated[
        Path,
        typer.Option(help="Reviewed Alpaca paper request JSON to run once."),
    ],
    from_env: Annotated[
        bool,
        typer.Option(help="Load Alpaca paper credentials from QUANT_* env."),
    ] = False,
) -> None:
    """Run one reviewed semantic-target request against Alpaca paper."""
    if not from_env:
        raise typer.BadParameter(
            "--from-env is required for Alpaca paper credentials"
        )
    current_time = _current_utc()
    if not _is_regular_us_equity_session(current_time):
        raise typer.BadParameter(
            "regular US equity session is closed; refusing to submit or "
            "queue an Alpaca paper market order"
        )
    try:
        config = _load_alpaca_paper_config_from_env()
        result = run_semantic_target_alpaca_paper_operator_request(
            request_path=request_path,
            broker_client=AlpacaPaperBrokerClient(config=config),
            evaluated_at=current_time,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Execution plan: {result.plan.execution_plan_id}")
    typer.echo(f"Status: {result.status.value}")
    if result.plan.order_request is None:
        typer.echo("Order: none")
    else:
        order = result.plan.order_request
        typer.echo(
            f"Order: {order.side.value} {order.quantity} {order.symbol}"
        )
    if result.reconciliation is None:
        typer.echo("Reconciliation: not written")
    else:
        typer.echo(f"Reconciliation: {result.reconciliation.status.value}")
        typer.echo(f"Differences: {len(result.reconciliation.differences)}")
    if result.status != ExecutionPlanStatus.SATISFIED:
        raise typer.Exit(code=1)


@semantic_target_app.command("prepare-alpaca-paper-request")
def semantic_target_prepare_alpaca_paper_request(
    request_id: Annotated[
        str,
        typer.Option(help="Safe ID for the generated Alpaca paper request."),
    ],
    source_request_path: Annotated[
        Path,
        typer.Option(help="Reviewed local semantic-paper request JSON."),
    ],
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for prepared Alpaca paper inputs."),
    ] = Path("data/semantic-target/alpaca-paper-requests"),
    paper_output_root: Annotated[
        Path,
        typer.Option(help="Future output root for Alpaca paper evidence."),
    ] = Path("data/semantic-target/alpaca-paper"),
    max_order_notional: Annotated[
        float,
        typer.Option(help="Reviewed maximum notional for this request."),
    ] = 1_000.0,
    allowed_max_quantity: Annotated[
        float,
        typer.Option(help="Reviewed maximum absolute target quantity."),
    ] = 1.0,
    valid_for_seconds: Annotated[
        int,
        typer.Option(help="How long the prepared request remains valid."),
    ] = 900,
) -> None:
    """Prepare one reviewed Alpaca paper request without broker access."""
    try:
        bundle = prepare_semantic_target_alpaca_paper_request(
            request_id=request_id,
            source_request_path=source_request_path,
            output_root=output_root,
            paper_output_root=paper_output_root / request_id,
            max_order_notional=Decimal(str(max_order_notional)),
            allowed_max_quantity=Decimal(str(allowed_max_quantity)),
            valid_for_seconds=valid_for_seconds,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {bundle.request_path}")
    typer.echo(f"Source request: {bundle.source_request_path}")
    typer.echo(f"Symbol: {bundle.symbol}")
    typer.echo(f"Approved target: {bundle.approved_target_quantity}")
    typer.echo(f"Reference price: {bundle.reference_price:,.2f}")
    typer.echo(f"Max order notional: {bundle.max_order_notional}")
    typer.echo(f"Valid until: {bundle.valid_until.isoformat()}")
    typer.echo(f"Paper output root: {bundle.paper_output_root}")
    typer.echo("Prepared only. No Alpaca API call was made.")


@dry_run_app.command("autonomous-finite-loop")
def dry_run_autonomous_finite_loop(
    manifest_path: Annotated[
        Path,
        typer.Option(help="Exact finite autonomous dry-run manifest."),
    ],
    output_root: Annotated[
        Path,
        typer.Option(help="Directory for finite-loop dry-run evidence."),
    ] = Path("data/semantic-target/autonomous-dry-run"),
) -> None:
    """Run one finite authorized dry-run request list and stop on block."""
    try:
        record = run_finite_autonomous_dry_run_loop(
            manifest_path=manifest_path,
            output_root=output_root,
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Loop: {record.loop_id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(
        f"Completed: {len(record.completed_run_ids)}/"
        f"{record.requested_run_count}"
    )
    for run_id, status in zip(
        record.completed_run_ids, record.run_statuses, strict=True
    ):
        typer.echo(f"Run: {run_id} ({status.value})")
    typer.echo(f"Reason: {record.reason}")
    typer.echo(
        f"Record: {output_root / 'loops' / f'{record.loop_id}.json'}"
    )
    if record.status == AutonomousDryRunStatus.BLOCKED:
        raise typer.Exit(code=1)


@dry_run_app.command("supervised-provider")
def dry_run_supervised_provider(
    request_path: Annotated[
        Path,
        typer.Option(help="Exact reviewed supervised-provider request."),
    ],
) -> None:
    """Assemble reviewed inputs and run one supervised dry-run cycle."""
    try:
        record = run_supervised_provider_operator_request(
            request_path=request_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {record.request_id}")
    typer.echo(f"Assembly: {record.assembly_id}")
    typer.echo(f"Service: {record.service_id}")
    typer.echo(f"Status: {record.service_status.value}")
    typer.echo(f"Record: {record.service_record_path}")
    if record.service_status != SupervisedDryRunServiceStatus.COMPLETED:
        raise typer.Exit(code=1)


@dry_run_app.command("supervised-provider-discover")
def dry_run_supervised_provider_discover(
    request_path: Annotated[
        Path,
        typer.Option(help="Exact reviewed discovery request."),
    ],
) -> None:
    """Run one reviewed discovery-only supervised-provider request."""
    try:
        record = run_supervised_provider_discovery_operator_request(
            request_path=request_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {record.request_id}")
    typer.echo(f"Discovery: {record.discovery_id}")
    typer.echo(f"Status: {record.discovery_status.value}")
    typer.echo(f"Result: {record.discovery_result_path}")
    if record.finite_manifest_path is not None:
        typer.echo(f"Finite manifest: {record.finite_manifest_path}")
    if record.discovery_status == SupervisedProviderDiscoveryStatus.BLOCKED:
        raise typer.Exit(code=1)


@dry_run_app.command("supervised-provider-discover-finite")
def dry_run_supervised_provider_discover_finite(
    request_path: Annotated[
        Path,
        typer.Option(help="Exact reviewed discovery-to-finite request."),
    ],
) -> None:
    """Run one reviewed discovery-to-finite supervised-provider request."""
    try:
        record = run_supervised_provider_discovery_loop_operator_request(
            request_path=request_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Request: {record.request_id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(f"Discovery record: {record.discovery_operator_record_path}")
    if record.finite_manifest_path is not None:
        typer.echo(f"Finite manifest: {record.finite_manifest_path}")
    if record.finite_loop_record_path is not None:
        typer.echo(f"Finite record: {record.finite_loop_record_path}")
    typer.echo(f"Reason: {record.reason}")
    if record.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED:
        raise typer.Exit(code=1)


@dry_run_app.command("supervised-provider-finite")
def dry_run_supervised_provider_finite(
    manifest_path: Annotated[
        Path,
        typer.Option(help="Exact finite supervised-provider manifest."),
    ],
) -> None:
    """Run one finite ordered list of fresh supervised-provider requests."""
    try:
        record = run_finite_supervised_provider_loop(
            manifest_path=manifest_path
        )
    except (OSError, ValueError) as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(f"Loop: {record.loop_id}")
    typer.echo(f"Status: {record.status.value}")
    typer.echo(
        f"Completed: {len(record.completed_request_ids)}/"
        f"{record.requested_count}"
    )
    for request_id in record.completed_request_ids:
        typer.echo(f"Request: {request_id} (completed)")
    if record.blocked_request_id is not None:
        typer.echo(f"Blocked request: {record.blocked_request_id}")
    typer.echo(f"Reason: {record.reason}")
    if record.status == FiniteSupervisedProviderStatus.BLOCKED:
        raise typer.Exit(code=1)


@live_app.command("fake-order")
def live_fake_order(
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
        typer.Option(help="Reference market price for the fake live order."),
    ] = 100.0,
    client_order_id: Annotated[
        str,
        typer.Option(help="Idempotent client order ID."),
    ] = "fake-live-order",
    initial_cash: Annotated[
        float,
        typer.Option(help="Starting cash for the fake broker client."),
    ] = 100_000,
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode rehearsal."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for this fake live order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode rehearsal."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live order artifacts."),
    ] = Path("data/live/orders"),
    fill_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live account snapshot artifacts."),
    ] = Path("data/live/account_snapshots"),
) -> None:
    """Submit a safety-gated fake live order with no broker network calls."""
    check, resolved_safety_config = _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    _validate_live_order_notional(
        quantity=quantity,
        price=price,
        max_order_notional=resolved_safety_config.max_order_notional,
    )
    client = FakeLiveBrokerClient(
        initial_cash=initial_cash,
        broker_name=broker_name or "fake-live",
    )
    adapter = LiveBrokerAdapter(
        client=client,
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )
    record = adapter.submit_market_order(
        OrderRequest(symbol=symbol, side=side, quantity=quantity),
        reference_price=price,
        client_order_id=client_order_id,
        safety_check=check,
    )
    snapshot = adapter.account_snapshot()

    typer.echo(f"Live fake order: {record.id}")
    typer.echo(f"Status: {record.status.value}")
    if record.rejection_reason is not None:
        typer.echo(f"Rejection reason: {record.rejection_reason}")
    typer.echo(f"Broker: {record.broker_name}")
    typer.echo(f"Client order ID: {record.client_order_id}")
    typer.echo(f"Broker order ID: {record.broker_order_id}")
    typer.echo(f"Side: {record.request.side.value}")
    typer.echo(f"Quantity: {record.request.quantity}")
    typer.echo(f"Reference price: {record.reference_price:,.2f}")
    typer.echo(f"Notional: {record.notional:,.2f}")
    typer.echo(f"Cash: {snapshot.cash:,.2f}")
    typer.echo(f"Order records: {order_output_dir}")
    typer.echo(f"Fill records: {fill_output_dir}")
    typer.echo(f"Snapshot records: {snapshot_output_dir}")

    if record.status.value == "rejected":
        raise typer.Exit(code=1)


@live_app.command("fake-reconcile")
def live_fake_reconcile(
    symbol: Annotated[str, typer.Option(help="Symbol to reconcile.")] = "AAPL",
    side: Annotated[
        OrderSide,
        typer.Option(help="Order side used to rebuild fake broker truth."),
    ] = OrderSide.BUY,
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity used to rebuild fake broker truth."),
    ] = 1,
    price: Annotated[
        float,
        typer.Option(help="Reference price used to rebuild fake broker truth."),
    ] = 100.0,
    client_order_id: Annotated[
        str,
        typer.Option(help="Client order ID used to rebuild fake broker truth."),
    ] = "fake-live-order",
    initial_cash: Annotated[
        float,
        typer.Option(help="Starting cash for the fake broker truth."),
    ] = 100_000,
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode rehearsal."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for this fake live order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode rehearsal."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local live order artifacts."),
    ] = Path("data/live/orders"),
    fill_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local account snapshots."),
    ] = Path("data/live/account_snapshots"),
    output_path: Annotated[
        Path,
        typer.Option(help="Path where reconciliation report is written."),
    ] = Path("data/live/reconciliation/latest.json"),
    cash_tolerance: Annotated[
        float,
        typer.Option(help="Allowed cash and price difference."),
    ] = 0.01,
) -> None:
    """Reconcile local live artifacts against fake broker truth."""
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")
    check, resolved_safety_config = _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    _validate_live_order_notional(
        quantity=quantity,
        price=price,
        max_order_notional=resolved_safety_config.max_order_notional,
    )
    client = FakeLiveBrokerClient(
        initial_cash=initial_cash,
        broker_name=broker_name or "fake-live",
    )
    client.submit_market_order(
        OrderRequest(symbol=symbol, side=side, quantity=quantity),
        reference_price=price,
        client_order_id=client_order_id,
        safety_check=check,
    )
    report = reconcile_live_state(
        client=client,
        order_records_dir=order_records_dir,
        fill_records_dir=fill_records_dir,
        snapshot_records_dir=snapshot_records_dir,
        cash_tolerance=cash_tolerance,
    )
    report_path = write_live_reconciliation_report(report, output_path)

    typer.echo(f"Status: {report.status.value}")
    typer.echo(f"Differences: {report.difference_count}")
    for difference in report.differences:
        typer.echo(
            f"[{difference.field}] local={difference.local_value} "
            f"broker={difference.broker_value}: {difference.message}"
        )
    typer.echo(f"Observations: {report.observation_count}")
    for observation in report.observations:
        typer.echo(
            f"[{observation.field}] local={observation.local_value} "
            f"broker={observation.broker_value}: {observation.message}"
        )
    typer.echo(f"Report: {report_path}")

    if not report.passed:
        raise typer.Exit(code=1)


@live_app.command("alpaca-paper-order")
def live_alpaca_paper_order(
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
        typer.Option(help="Reference market price for safety/audit records."),
    ] = 100.0,
    client_order_id: Annotated[
        str,
        typer.Option(help="Idempotent client order ID."),
    ] = "alpaca-paper-order",
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for this paper order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live order artifacts."),
    ] = Path("data/live/orders"),
    fill_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live account snapshot artifacts."),
    ] = Path("data/live/account_snapshots"),
) -> None:
    """Submit a safety-gated Alpaca paper market order."""
    check, resolved_safety_config = _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    _validate_live_order_notional(
        quantity=quantity,
        price=price,
        max_order_notional=resolved_safety_config.max_order_notional,
    )
    config = _load_alpaca_paper_config_from_env()
    adapter = LiveBrokerAdapter(
        client=AlpacaPaperBrokerClient(config=config),
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )
    record = adapter.submit_market_order(
        OrderRequest(symbol=symbol, side=side, quantity=quantity),
        reference_price=price,
        client_order_id=client_order_id,
        safety_check=check,
    )
    snapshot = adapter.account_snapshot()

    typer.echo(f"Alpaca paper order: {record.id}")
    typer.echo(f"Status: {record.status.value}")
    if record.rejection_reason is not None:
        typer.echo(f"Rejection reason: {record.rejection_reason}")
    typer.echo(f"Broker: {record.broker_name}")
    typer.echo(f"Client order ID: {record.client_order_id}")
    typer.echo(f"Broker order ID: {record.broker_order_id}")
    typer.echo(f"Side: {record.request.side.value}")
    typer.echo(f"Quantity: {record.request.quantity}")
    typer.echo(f"Reference price: {record.reference_price:,.2f}")
    typer.echo(f"Notional: {record.notional:,.2f}")
    typer.echo(f"Cash: {snapshot.cash:,.2f}")
    typer.echo(f"Order records: {order_output_dir}")
    typer.echo(f"Fill records: {fill_output_dir}")
    typer.echo(f"Snapshot records: {snapshot_output_dir}")

    if record.status.value == "rejected":
        raise typer.Exit(code=1)


@live_app.command("alpaca-paper-rehearsal-order")
def live_alpaca_paper_rehearsal_order(
    symbol: Annotated[
        str,
        typer.Option(help="Reviewed non-protected symbol to buy."),
    ],
    reference_price: Annotated[
        float,
        typer.Option(help="Current reviewed price used by safety checks."),
    ],
    client_order_id: Annotated[
        str,
        typer.Option(help="Unique client order ID for this rehearsal."),
    ],
    protected_position: Annotated[
        list[str],
        typer.Option(
            help="Required signed broker position in SYMBOL=QUANTITY form."
        ),
    ],
    rehearsal_confirmation: Annotated[
        str | None,
        typer.Option(help="Separate confirmation phrase for this rehearsal."),
    ] = None,
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for this paper order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_poll_attempts: Annotated[
        int,
        typer.Option(help="Maximum broker order status checks."),
    ] = 5,
    order_poll_interval_seconds: Annotated[
        float,
        typer.Option(help="Seconds between broker order status checks."),
    ] = 1,
    cash_tolerance: Annotated[
        float,
        typer.Option(
            help="Allowed hard numeric reconciliation difference."
        ),
    ] = 0.01,
    order_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live order artifacts."),
    ] = Path("data/live/orders"),
    fill_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live account snapshot artifacts."),
    ] = Path("data/live/account_snapshots"),
    reconciliation_output_path: Annotated[
        Path,
        typer.Option(help="Path for the post-order reconciliation report."),
    ] = Path("data/live/reconciliation/latest.json"),
    rehearsal_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for dedicated rehearsal results."),
    ] = Path("data/live/rehearsals"),
) -> None:
    """Run one explicitly approved, evidence-producing Alpaca paper buy."""
    check, resolved_safety_config = _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    if rehearsal_confirmation != ALPACA_PAPER_REHEARSAL_CONFIRMATION:
        typer.echo("Blocked: rehearsal confirmation is missing")
        typer.echo(
            "Required rehearsal confirmation: "
            f"{ALPACA_PAPER_REHEARSAL_CONFIRMATION}"
        )
        raise typer.Exit(code=1)
    protected_positions = _parse_protected_positions(protected_position)

    # Credentials and the network-capable client are intentionally constructed
    # only after every locally checkable confirmation and input has passed.
    config = _load_alpaca_paper_config_from_env()
    try:
        result = run_alpaca_paper_order_rehearsal(
            client=AlpacaPaperBrokerClient(config=config),
            safety_check=check,
            symbol=symbol,
            reference_price=reference_price,
            client_order_id=client_order_id,
            protected_positions=protected_positions,
            confirmation=rehearsal_confirmation,
            order_output_dir=order_output_dir,
            fill_output_dir=fill_output_dir,
            snapshot_output_dir=snapshot_output_dir,
            reconciliation_output_path=reconciliation_output_path,
            rehearsal_output_dir=rehearsal_output_dir,
            max_order_notional=resolved_safety_config.max_order_notional,
            order_poll_attempts=order_poll_attempts,
            order_poll_interval_seconds=order_poll_interval_seconds,
            cash_tolerance=cash_tolerance,
        )
    except LiveRehearsalBlockedError as exc:
        typer.echo(f"Blocked: {exc}")
        raise typer.Exit(code=1) from exc

    typer.echo(f"Rehearsal status: {result.status.value}")
    typer.echo(f"Client order ID: {result.client_order_id}")
    typer.echo(f"Order status: {result.order_status.value}")
    typer.echo(f"Reconciliation passed: {result.reconciliation_passed}")
    typer.echo(f"Rehearsal records: {rehearsal_output_dir}")
    if result.failure_reason is not None:
        typer.echo(f"Failure reason: {result.failure_reason}")
        raise typer.Exit(code=1)


@live_app.command("alpaca-paper-snapshot")
def live_alpaca_paper_snapshot(
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional safety setting."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    snapshot_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live account snapshot artifacts."),
    ] = Path("data/live/account_snapshots"),
) -> None:
    """Fetch a safety-gated Alpaca paper account snapshot."""
    _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    config = _load_alpaca_paper_config_from_env()
    client = AlpacaPaperBrokerClient(config=config)
    snapshot = client.account_snapshot()
    snapshot_path = write_live_account_snapshot(
        snapshot,
        snapshot_output_dir,
    )

    typer.echo(f"Alpaca paper account snapshot: {snapshot.id}")
    typer.echo(f"Broker: {snapshot.broker_name}")
    typer.echo(f"Account ID: {snapshot.account_id}")
    typer.echo(f"Cash: {snapshot.cash:,.2f}")
    typer.echo(f"Buying power: {snapshot.buying_power:,.2f}")
    typer.echo(f"Positions: {len(snapshot.positions)}")
    typer.echo(f"Snapshot: {snapshot_path}")


@live_app.command("alpaca-paper-reconcile")
def live_alpaca_paper_reconcile(
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional safety setting."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local live order artifacts."),
    ] = Path("data/live/orders"),
    fill_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local account snapshots."),
    ] = Path("data/live/account_snapshots"),
    output_path: Annotated[
        Path,
        typer.Option(help="Path where reconciliation report is written."),
    ] = Path("data/live/reconciliation/latest.json"),
    cash_tolerance: Annotated[
        float,
        typer.Option(
            help="Allowed hard numeric reconciliation difference."
        ),
    ] = 0.01,
) -> None:
    """Reconcile local live artifacts against Alpaca paper broker truth."""
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")
    _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    config = _load_alpaca_paper_config_from_env()
    client = AlpacaPaperBrokerClient(config=config)
    report = reconcile_live_state(
        client=client,
        order_records_dir=order_records_dir,
        fill_records_dir=fill_records_dir,
        snapshot_records_dir=snapshot_records_dir,
        cash_tolerance=cash_tolerance,
    )
    report_path = write_live_reconciliation_report(report, output_path)

    typer.echo(f"Status: {report.status.value}")
    typer.echo(f"Differences: {report.difference_count}")
    for difference in report.differences:
        typer.echo(
            f"[{difference.field}] local={difference.local_value} "
            f"broker={difference.broker_value}: {difference.message}"
        )
    typer.echo(f"Observations: {report.observation_count}")
    for observation in report.observations:
        typer.echo(
            f"[{observation.field}] local={observation.local_value} "
            f"broker={observation.broker_value}: {observation.message}"
        )
    typer.echo(f"Report: {report_path}")

    if not report.passed:
        raise typer.Exit(code=1)


@live_app.command("alpaca-paper-refresh-orders")
def live_alpaca_paper_refresh_orders(
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional safety setting."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
    order_records_dir: Annotated[
        Path,
        typer.Option(help="Directory containing local live order artifacts."),
    ] = Path("data/live/orders"),
    fill_records_dir: Annotated[
        Path,
        typer.Option(help="Directory for fills discovered during refresh."),
    ] = Path("data/live/fills"),
) -> None:
    """Refresh local Alpaca paper order artifacts from broker truth."""
    _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    config = _load_alpaca_paper_config_from_env()
    client = AlpacaPaperBrokerClient(config=config)
    adapter = LiveBrokerAdapter(
        client=client,
        order_output_dir=order_records_dir,
        fill_output_dir=fill_records_dir,
    )
    refreshed_count = 0
    for order_record in load_live_order_records(order_records_dir):
        adapter.refresh_order_record(order_record)
        refreshed_count += 1

    typer.echo(f"Refreshed orders: {refreshed_count}")
    typer.echo(f"Order records: {order_records_dir}")
    typer.echo(f"Fill records: {fill_records_dir}")


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


@schedule_app.command("dry-run-signal")
def schedule_dry_run_signal(
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
    dry_run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where dry-run order records are written."),
    ] = Path("data/dry_run/orders"),
    run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where scheduler run records are written."),
    ] = Path("data/scheduler/dry-run"),
) -> None:
    """Run a finite scheduled strategy-to-dry-run execution loop."""
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if iterations < 1:
        raise typer.BadParameter("iterations must be at least 1")
    if interval_seconds < 0:
        raise typer.BadParameter("interval-seconds must be non-negative")

    if not skip_validation:
        _validate_or_exit(data, symbol, min_rows=min_rows)

    config = TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    check = evaluate_trading_safety(config)
    if not check.allowed:
        raise typer.Exit(code=1)

    runner = SchedulerRunner(output_dir=run_output_dir)
    signal_strategy = MomentumStrategy()
    adapter = DryRunBrokerAdapter(broker_name=broker_name)

    def task() -> ScheduledTaskResult:
        # Reload inside each scheduled attempt to match paper signal behavior.
        prices = load_price_csv(data, symbol)
        decision, record = execute_latest_signal_dry_run(
            strategy=signal_strategy,
            prices=prices,
            broker=adapter,
            quantity=quantity,
            safety_check=check,
        )
        message = f"dry-run signal {decision.action}"
        if record is None:
            message = f"{message}: no order intended"
            return ScheduledTaskResult(message=message)

        record_path = write_dry_run_order_record(record, dry_run_output_dir)
        return ScheduledTaskResult(
            message=message,
            artifact_paths=(str(record_path),),
        )

    records = runner.run_loop(
        task_name="dry-run-signal",
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
    typer.echo(f"Dry-run records: {dry_run_output_dir}")

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


@workflow_app.command("dry-run-refresh")
def workflow_dry_run_refresh(
    symbol: Annotated[
        str,
        typer.Option(help="Symbol to refresh and dry-run."),
    ] = "AAPL",
    start: Annotated[
        str,
        typer.Option(help="Refresh start date, YYYY-MM-DD."),
    ] = "2024-01-01",
    end: Annotated[
        str | None,
        typer.Option(help="Optional refresh end date, YYYY-MM-DD."),
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
        typer.Option(help="Share quantity for actionable dry-run signals."),
    ] = 1,
    broker_name: Annotated[
        str,
        typer.Option(help="Broker name to include in dry-run records."),
    ] = "dry-run",
    iterations: Annotated[
        int,
        typer.Option(help="Number of scheduled dry-run signal runs."),
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
    ] = Path("data/workflows/dry-run-refresh"),
    dry_run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where dry-run order records are written."),
    ] = Path("data/dry_run/orders"),
    run_output_dir: Annotated[
        Path,
        typer.Option(help="Directory where scheduler run records are written."),
    ] = Path("data/scheduler/dry-run"),
    paper_signal_dir: Annotated[
        Path,
        typer.Option(help="Directory containing paper signal records."),
    ] = Path("data/paper/signals"),
    comparison_output_path: Annotated[
        Path,
        typer.Option(help="Path where comparison report is written."),
    ] = Path("data/dry_run/comparison/latest.json"),
    publish_status_path: Annotated[
        Path | None,
        typer.Option(help="Optional dashboard status JSON path to publish."),
    ] = None,
    health_run_records_dir: Annotated[
        Path | None,
        typer.Option(help="Optional run records dir for published health."),
    ] = None,
    paper_state_path: Annotated[
        Path,
        typer.Option(help="Paper state path used for published health."),
    ] = Path("data/paper/state/default.json"),
    logs_dir: Annotated[
        Path,
        typer.Option(help="Logs directory used for published health."),
    ] = Path("logs"),
    lock_path: Annotated[
        Path,
        typer.Option(help="Lock file that prevents overlapping workflow runs."),
    ] = Path("data/locks/dry-run-refresh.lock"),
    lock_stale_after_seconds: Annotated[
        int,
        typer.Option(help="Seconds before an existing workflow lock is stale."),
    ] = 7200,
) -> None:
    """Refresh data, run dry-run signals, compare, and optionally publish."""
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if iterations < 1:
        raise typer.BadParameter("iterations must be at least 1")
    if interval_seconds < 0:
        raise typer.BadParameter("interval-seconds must be non-negative")
    if provider != "yfinance":
        raise typer.BadParameter("Only yfinance is implemented right now.")

    try:
        record = run_dry_run_refresh_workflow(
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
            broker_name=broker_name,
            iterations=iterations,
            interval_seconds=interval_seconds,
            min_rows=min_rows,
            dry_run_output_dir=dry_run_output_dir,
            run_output_dir=run_output_dir,
            paper_signal_dir=paper_signal_dir,
            comparison_output_path=comparison_output_path,
            publish_status_path=publish_status_path,
            health_run_records_dir=health_run_records_dir,
            paper_state_path=paper_state_path,
            logs_dir=logs_dir,
            lock_path=lock_path,
            lock_stale_after_seconds=lock_stale_after_seconds,
        )
    except WorkflowRunFailed as exc:
        _print_workflow_record(exc.record, workflow_output_dir)
        raise typer.Exit(code=1) from exc

    _print_workflow_record(record, workflow_output_dir)


@workflow_app.command("alpaca-paper-refresh")
def workflow_alpaca_paper_refresh(
    symbol: Annotated[
        str,
        typer.Option(help="Symbol to refresh and trade."),
    ] = "AAPL",
    start: Annotated[
        str,
        typer.Option(help="Refresh start date, YYYY-MM-DD."),
    ] = "2024-01-01",
    end: Annotated[
        str | None,
        typer.Option(help="Optional refresh end date, YYYY-MM-DD."),
    ] = None,
    provider: Annotated[
        str,
        typer.Option(help="Data provider name."),
    ] = "yfinance",
    strategy: Annotated[
        str,
        typer.Option(help="Strategy name to run after refresh."),
    ] = "momentum",
    quantity: Annotated[
        int,
        typer.Option(help="Share quantity for actionable signals."),
    ] = 1,
    live_trading_enabled: Annotated[
        bool,
        typer.Option(help="Explicitly enable live-mode broker access."),
    ] = False,
    live_trading_confirmation: Annotated[
        str | None,
        typer.Option(help="Required live-mode confirmation phrase."),
    ] = None,
    max_order_notional: Annotated[
        float | None,
        typer.Option(help="Maximum allowed notional for this paper order."),
    ] = None,
    broker_name: Annotated[
        str | None,
        typer.Option(help="Broker name required for live-mode broker access."),
    ] = None,
    from_env: Annotated[
        bool,
        typer.Option(help="Load safety settings from QUANT_* env vars."),
    ] = False,
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
    ] = Path("data/workflows/alpaca-paper-refresh"),
    order_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live order artifacts."),
    ] = Path("data/live/orders"),
    fill_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live fill artifacts."),
    ] = Path("data/live/fills"),
    snapshot_output_dir: Annotated[
        Path,
        typer.Option(help="Directory for live account snapshot artifacts."),
    ] = Path("data/live/account_snapshots"),
    reconciliation_output_path: Annotated[
        Path,
        typer.Option(help="Path where reconciliation report is written."),
    ] = Path("data/live/reconciliation/latest.json"),
    cash_tolerance: Annotated[
        float,
        typer.Option(help="Allowed cash and price difference."),
    ] = 0.01,
    order_poll_attempts: Annotated[
        int,
        typer.Option(help="Maximum broker order refresh attempts."),
    ] = 5,
    order_poll_interval_seconds: Annotated[
        float,
        typer.Option(help="Seconds between broker order refresh attempts."),
    ] = 1,
    lock_path: Annotated[
        Path,
        typer.Option(help="Lock file that prevents overlapping workflow runs."),
    ] = Path("data/locks/alpaca-paper-refresh.lock"),
    lock_stale_after_seconds: Annotated[
        int,
        typer.Option(help="Seconds before an existing workflow lock is stale."),
    ] = 7200,
) -> None:
    """Refresh data, submit one Alpaca paper signal, then reconcile."""
    if strategy != "momentum":
        raise typer.BadParameter("Only momentum is implemented right now.")
    if quantity < 1:
        raise typer.BadParameter("quantity must be at least 1")
    if cash_tolerance < 0:
        raise typer.BadParameter("cash-tolerance must be non-negative")
    if order_poll_attempts < 1:
        raise typer.BadParameter("order-poll-attempts must be at least 1")
    if order_poll_interval_seconds < 0:
        raise typer.BadParameter(
            "order-poll-interval-seconds must be non-negative"
        )
    if provider != "yfinance":
        raise typer.BadParameter("Only yfinance is implemented right now.")

    check, resolved_safety_config = _live_safety_check_or_exit(
        from_env=from_env,
        live_trading_enabled=live_trading_enabled,
        live_trading_confirmation=live_trading_confirmation,
        max_order_notional=max_order_notional,
        broker_name=broker_name,
    )
    safety_config = resolved_safety_config.model_copy(
        update={
            "mode": check.mode,
            "live_trading_enabled": True,
            "live_trading_confirmation": LIVE_TRADING_CONFIRMATION,
            "broker_name": broker_name or resolved_safety_config.broker_name,
        }
    )
    config = _load_alpaca_paper_config_from_env()

    try:
        record = run_alpaca_paper_refresh_workflow(
            provider=YFinanceMarketBarProvider(),
            broker_client=AlpacaPaperBrokerClient(config=config),
            safety_config=safety_config,
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
            min_rows=min_rows,
            order_output_dir=order_output_dir,
            fill_output_dir=fill_output_dir,
            snapshot_output_dir=snapshot_output_dir,
            reconciliation_output_path=reconciliation_output_path,
            cash_tolerance=cash_tolerance,
            order_poll_attempts=order_poll_attempts,
            order_poll_interval_seconds=order_poll_interval_seconds,
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
    check_paper_service: Annotated[
        bool,
        typer.Option(
            help="Check the original paper scheduler/signal/state lane."
        ),
    ] = True,
    check_comparison: Annotated[
        bool,
        typer.Option(help="Check paper-vs-dry-run comparison report."),
    ] = False,
    comparison_report_path: Annotated[
        Path,
        typer.Option(help="Path to paper-vs-dry-run comparison report."),
    ] = Path("data/dry_run/comparison/latest.json"),
    check_alpaca_paper: Annotated[
        bool,
        typer.Option(help="Check Alpaca paper workflow and reconciliation."),
    ] = False,
    alpaca_paper_workflow_records_dir: Annotated[
        Path,
        typer.Option(
            help="Directory containing Alpaca paper workflow records."
        ),
    ] = Path("data/workflows/alpaca-paper-refresh"),
    alpaca_paper_reconciliation_report_path: Annotated[
        Path,
        typer.Option(help="Path to Alpaca paper reconciliation report."),
    ] = Path("data/live/reconciliation/latest.json"),
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
        check_paper_service=check_paper_service,
        check_comparison=check_comparison,
        comparison_report_path=(
            comparison_report_path if check_comparison else None
        ),
        check_alpaca_paper=check_alpaca_paper,
        alpaca_paper_workflow_records_dir=(
            alpaca_paper_workflow_records_dir
            if check_alpaca_paper
            else None
        ),
        alpaca_paper_reconciliation_report_path=(
            alpaca_paper_reconciliation_report_path
            if check_alpaca_paper
            else None
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
    check_paper_service: Annotated[
        bool,
        typer.Option(
            help="Check the original paper scheduler/signal/state lane."
        ),
    ] = True,
    check_comparison: Annotated[
        bool,
        typer.Option(help="Check paper-vs-dry-run comparison report."),
    ] = True,
    comparison_report_path: Annotated[
        Path,
        typer.Option(help="Path to paper-vs-dry-run comparison report."),
    ] = Path("data/dry_run/comparison/latest.json"),
    check_alpaca_paper: Annotated[
        bool,
        typer.Option(help="Check Alpaca paper workflow and reconciliation."),
    ] = False,
    alpaca_paper_workflow_records_dir: Annotated[
        Path,
        typer.Option(
            help="Directory containing Alpaca paper workflow records."
        ),
    ] = Path("data/workflows/alpaca-paper-refresh"),
    alpaca_paper_reconciliation_report_path: Annotated[
        Path,
        typer.Option(help="Path to Alpaca paper reconciliation report."),
    ] = Path("data/live/reconciliation/latest.json"),
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
        reconcile_state=reconcile_state and check_paper_service,
        initial_cash=initial_cash,
        cash_tolerance=cash_tolerance,
        reconciliation_report_path=None,
        check_paper_service=check_paper_service,
        check_comparison=check_comparison,
        comparison_report_path=(
            comparison_report_path if check_comparison else None
        ),
        check_alpaca_paper=check_alpaca_paper,
        alpaca_paper_workflow_records_dir=(
            alpaca_paper_workflow_records_dir
            if check_alpaca_paper
            else None
        ),
        alpaca_paper_reconciliation_report_path=(
            alpaca_paper_reconciliation_report_path
            if check_alpaca_paper
            else None
        ),
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


@ops_app.command("publish-knowledge")
def ops_publish_knowledge(
    docs_dir: Annotated[
        Path,
        typer.Option(help="Directory containing documentation Markdown files."),
    ] = Path("docs"),
    output_path: Annotated[
        Path,
        typer.Option(help="Knowledge index JSON output path."),
    ] = Path("site/knowledge_index.json"),
) -> None:
    """Publish a searchable knowledge index for the static dashboard."""
    import json

    from quant.web.docs_index import build_docs_index

    manifest = build_docs_index(docs_dir)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic write: write to temp file, then rename
    tmp_path = output_path.with_suffix(".json.tmp")
    tmp_path.write_text(
        json.dumps(manifest.to_dict(), indent=2, default=str),
        encoding="utf-8",
    )
    tmp_path.rename(output_path)
    typer.echo(f"Knowledge index: {output_path}")
    typer.echo(f"Documents: {len(manifest.docs)}")
    typer.echo(f"Collections: {', '.join(manifest.collections)}")


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


def _live_safety_check_or_exit(
    *,
    from_env: bool,
    live_trading_enabled: bool,
    live_trading_confirmation: str | None,
    max_order_notional: float | None,
    broker_name: str | None,
) -> tuple[TradingSafetyCheck, TradingSafetyConfig]:
    if from_env:
        try:
            config = load_trading_safety_config_from_env()
        except ValueError as exc:
            raise typer.BadParameter(str(exc)) from exc
    else:
        config = TradingSafetyConfig(
            mode=TradingMode.LIVE,
            live_trading_enabled=live_trading_enabled,
            live_trading_confirmation=live_trading_confirmation,
            max_order_notional=max_order_notional,
            broker_name=broker_name,
        )

    check = evaluate_trading_safety(config)
    if not check.allowed:
        typer.echo("Allowed: False")
        for issue in check.issues:
            typer.echo(f"- {issue}")
        typer.echo(f"Required confirmation: {LIVE_TRADING_CONFIRMATION}")
        raise typer.Exit(code=1)
    return check, config


def _validate_live_order_notional(
    *,
    quantity: int,
    price: float,
    max_order_notional: float | None,
) -> None:
    if price <= 0:
        raise typer.BadParameter("price must be positive")
    notional = quantity * price
    if max_order_notional is not None and notional > max_order_notional:
        raise typer.BadParameter(
            "order notional exceeds max-order-notional"
        )


def _parse_protected_positions(values: list[str]) -> dict[str, int]:
    """Parse explicit signed position invariants without accepting ambiguity."""
    positions: dict[str, int] = {}
    for value in values:
        symbol, separator, raw_quantity = value.partition("=")
        normalized_symbol = symbol.strip().upper()
        if not separator or not normalized_symbol:
            raise typer.BadParameter(
                "protected-position must use SYMBOL=QUANTITY"
            )
        if normalized_symbol in positions:
            raise typer.BadParameter(
                f"duplicate protected position: {normalized_symbol}"
            )
        try:
            quantity = int(raw_quantity)
        except ValueError as exc:
            raise typer.BadParameter(
                "protected-position quantity must be a signed integer"
            ) from exc
        if quantity == 0:
            raise typer.BadParameter(
                "protected-position quantity must be non-zero"
            )
        positions[normalized_symbol] = quantity
    if not positions:
        raise typer.BadParameter("at least one protected-position is required")
    return positions


def _load_alpaca_paper_config_from_env() -> AlpacaPaperConfig:
    api_key = _required_env("QUANT_ALPACA_PAPER_API_KEY")
    secret_key = _required_env("QUANT_ALPACA_PAPER_SECRET_KEY")
    account_id = _required_env("QUANT_ALPACA_PAPER_ACCOUNT_ID")
    url_override = os.environ.get("QUANT_ALPACA_PAPER_URL_OVERRIDE")
    return AlpacaPaperConfig(
        api_key=api_key,
        secret_key=secret_key,
        account_id=account_id,
        url_override=url_override or None,
    )


def _required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value == "":
        raise typer.BadParameter(f"{name} is missing")
    return value


def _current_utc() -> datetime:
    return datetime.now(UTC)


def _is_regular_us_equity_session(moment: datetime) -> bool:
    eastern = moment.astimezone(ZoneInfo("America/New_York"))
    session_date = eastern.date()
    if session_date.weekday() >= 5:
        return False
    if session_date in _us_equity_holidays(session_date.year):
        return False
    open_time = time(9, 30)
    close_time = (
        time(13, 0)
        if session_date in _us_equity_early_closes(session_date.year)
        else time(16, 0)
    )
    return open_time <= eastern.time() < close_time


def _us_equity_holidays(year: int) -> set[date]:
    return {
        _observed_fixed_holiday(year, 1, 1),
        _nth_weekday(year, 1, 0, 3),
        _nth_weekday(year, 2, 0, 3),
        _good_friday(year),
        _last_weekday(year, 5, 0),
        _observed_fixed_holiday(year, 6, 19),
        _observed_fixed_holiday(year, 7, 4),
        _nth_weekday(year, 9, 0, 1),
        _nth_weekday(year, 11, 3, 4),
        _observed_fixed_holiday(year, 12, 25),
    }


def _us_equity_early_closes(year: int) -> set[date]:
    closes = {_nth_weekday(year, 11, 3, 4) + timedelta(days=1)}
    christmas_eve = date(year, 12, 24)
    if christmas_eve.weekday() < 5:
        closes.add(christmas_eve)
    july_fourth = date(year, 7, 4)
    july_third = date(year, 7, 3)
    if july_fourth.weekday() in {4, 5} and july_third.weekday() < 5:
        closes.add(july_third)
    return closes - _us_equity_holidays(year)


def _observed_fixed_holiday(year: int, month: int, day: int) -> date:
    holiday = date(year, month, day)
    if holiday.weekday() == 5:
        return holiday - timedelta(days=1)
    if holiday.weekday() == 6:
        return holiday + timedelta(days=1)
    return holiday


def _nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    current = date(year, month, 1)
    offset = (weekday - current.weekday()) % 7
    return current + timedelta(days=offset + 7 * (n - 1))


def _last_weekday(year: int, month: int, weekday: int) -> date:
    if month == 12:
        current = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        current = date(year, month + 1, 1) - timedelta(days=1)
    return current - timedelta(days=(current.weekday() - weekday) % 7)


def _good_friday(year: int) -> date:
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    line = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * line) // 451
    month = (h + line - 7 * m + 114) // 31
    day = ((h + line - 7 * m + 114) % 31) + 1
    return date(year, month, day) - timedelta(days=2)


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
    typer.echo(
        "Comparison: "
        f"status={report.comparison_status} "
        "differences="
        f"{_format_health_value(report.comparison_difference_count)} "
        f"({_format_health_value(report.comparison_report_path)})"
    )
    typer.echo(
        "Alpaca paper: "
        f"workflow={report.alpaca_paper_workflow_status} "
        f"reconciliation={report.alpaca_paper_reconciliation_status} "
        "differences="
        f"{_format_health_value(
            report.alpaca_paper_reconciliation_difference_count
        )} "
        f"({_format_health_value(
            report.alpaca_paper_reconciliation_report_path
        )})"
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
    typer.echo(
        "Latest signal: "
        f"{_format_health_value(record.latest_signal_action)}"
    )
    typer.echo(
        "Broker submission attempted: "
        f"{_format_health_value(record.broker_submission_attempted)}"
    )
    typer.echo(
        "Broker submission skipped reason: "
        f"{_format_health_value(record.broker_submission_skipped_reason)}"
    )
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


@web_app.command("serve")
def web_serve(
    host: Annotated[
        str,
        typer.Option(help="Bind address."),
    ] = "127.0.0.1",
    port: Annotated[
        int,
        typer.Option(help="Bind port."),
    ] = 8000,
    reload: Annotated[
        bool,
        typer.Option(help="Enable auto-reload for development."),
    ] = False,
) -> None:
    """Start the web console server."""
    from quant.web.serve import serve

    serve(host=host, port=port, reload=reload)


if __name__ == "__main__":
    app()
