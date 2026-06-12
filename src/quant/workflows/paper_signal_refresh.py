from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import sleep

from quant.data import ingest_market_bars, load_price_csv
from quant.data.providers.base import DataProvider
from quant.execution import (
    DryRunBrokerAdapter,
    LiveBrokerAdapter,
    LiveBrokerClient,
    PaperBrokerAdapter,
    check_projected_order_risk,
    check_short_sale_availability,
    compare_paper_signal_to_dry_run_order,
    decide_latest_signal,
    evaluate_trading_safety,
    execute_latest_signal,
    execute_latest_signal_dry_run,
    latest_json,
    load_paper_broker_state,
    opens_or_increases_short,
    plan_target_position_order,
    reconcile_live_state,
    save_paper_broker_state,
    write_dry_run_order_record,
    write_live_reconciliation_report,
    write_paper_dry_run_comparison_report,
    write_paper_signal_record,
)
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    PaperSignalAction,
    Position,
    TradingMode,
    TradingSafetyConfig,
)
from quant.models.ingestion import IngestArtifactPaths, IngestRequest
from quant.models.scheduler import ScheduledRunRecord, ScheduledTaskResult
from quant.models.workflow import DataRefreshWorkflowRecord, WorkflowRunStatus
from quant.operations import (
    FileLock,
    build_dashboard_health_status,
    build_health_report,
    write_dashboard_health_status,
)
from quant.scheduler import SchedulerRunner
from quant.strategies import MomentumStrategy


class WorkflowRunFailed(RuntimeError):
    def __init__(self, record: DataRefreshWorkflowRecord) -> None:
        super().__init__(record.message)
        self.record = record


class _AlpacaPaperSignalFailed(RuntimeError):
    def __init__(
        self,
        message: str,
        outcome: "_AlpacaPaperSignalRunOutcome",
    ) -> None:
        super().__init__(message)
        self.outcome = outcome


@dataclass(frozen=True)
class _AlpacaPaperSignalRunOutcome:
    artifact_paths: tuple[str, ...] = ()
    latest_signal_action: str | None = None
    latest_signal_reason: str | None = None
    latest_signal_market_price: float | None = None
    broker_submission_attempted: bool | None = None
    broker_submission_skipped_reason: str | None = None
    broker_position_quantity_before: int | None = None
    strategy_target_quantity: int | None = None
    planned_order_side: str | None = None
    planned_order_quantity: int | None = None
    order_artifact_paths: tuple[str, ...] = ()
    fill_artifact_paths: tuple[str, ...] = ()
    snapshot_artifact_paths: tuple[str, ...] = ()
    reconciliation_report_path: str | None = None


def run_paper_signal_refresh_workflow(
    *,
    provider: DataProvider,
    symbol: str,
    start: str,
    end: str | None,
    raw_dir: Path,
    normalized_dir: Path,
    validation_dir: Path,
    metadata_dir: Path,
    workflow_output_dir: Path,
    strategy: str,
    quantity: int,
    initial_cash: float,
    initial_position_quantity: int,
    initial_position_price: float,
    iterations: int,
    interval_seconds: float,
    min_rows: int,
    signal_output_dir: Path,
    state_path: Path,
    run_output_dir: Path,
    lock_path: Path | None = None,
    lock_stale_after_seconds: int = 7200,
) -> DataRefreshWorkflowRecord:
    """Refresh data, validate it, then run the paper-signal scheduler."""
    started_at = datetime.now(UTC)
    ingest_artifact: IngestArtifactPaths | None = None
    scheduler_records: tuple[ScheduledRunRecord, ...] = ()
    lock_owner: str | None = None

    try:
        lock = (
            FileLock(
                path=lock_path,
                lock_name="paper-signal-refresh",
                stale_after_seconds=lock_stale_after_seconds,
            )
            if lock_path is not None
            else None
        )
        if lock is not None:
            lock_owner = lock.acquire().owner

        try:
            if strategy != "momentum":
                raise ValueError("Only momentum is implemented right now.")

            request = IngestRequest(symbols=(symbol,), start=start, end=end)
            artifacts = ingest_market_bars(
                provider,
                request,
                raw_root=raw_dir,
                normalized_root=normalized_dir,
                validation_root=validation_dir,
                metadata_root=metadata_dir,
                validate=True,
                min_rows=min_rows,
            )
            ingest_artifact = _single_artifact(artifacts)
            if ingest_artifact.validation_passed is not True:
                raise ValueError(
                    "data refresh validation failed; paper signal was not run"
                )

            scheduler_records = _run_paper_signal_loop(
                data=Path(ingest_artifact.normalized_path),
                symbol=symbol,
                quantity=quantity,
                initial_cash=initial_cash,
                initial_position_quantity=initial_position_quantity,
                initial_position_price=initial_position_price,
                iterations=iterations,
                interval_seconds=interval_seconds,
                signal_output_dir=signal_output_dir,
                state_path=state_path,
                run_output_dir=run_output_dir,
            )
            failed_runs = [
                record
                for record in scheduler_records
                if record.status.value == "failed"
            ]
            if failed_runs:
                message = (
                    f"{len(failed_runs)} paper signal scheduler runs failed"
                )
                status = WorkflowRunStatus.FAILED
            else:
                message = "data refreshed and paper signal workflow completed"
                status = WorkflowRunStatus.SUCCEEDED
        finally:
            if lock is not None:
                lock.release()

        record = _build_record(
            status=status,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=message,
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        if status == WorkflowRunStatus.FAILED:
            raise WorkflowRunFailed(record)
        return record
    except WorkflowRunFailed:
        raise
    except Exception as exc:
        record = _build_record(
            status=WorkflowRunStatus.FAILED,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=str(exc),
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        raise WorkflowRunFailed(record) from exc


def run_dry_run_refresh_workflow(
    *,
    provider: DataProvider,
    symbol: str,
    start: str,
    end: str | None,
    raw_dir: Path,
    normalized_dir: Path,
    validation_dir: Path,
    metadata_dir: Path,
    workflow_output_dir: Path,
    strategy: str,
    quantity: int,
    broker_name: str,
    iterations: int,
    interval_seconds: float,
    min_rows: int,
    dry_run_output_dir: Path,
    run_output_dir: Path,
    paper_signal_dir: Path,
    comparison_output_path: Path,
    publish_status_path: Path | None = None,
    health_run_records_dir: Path | None = None,
    paper_state_path: Path = Path("data/paper/state/default.json"),
    logs_dir: Path = Path("logs"),
    lock_path: Path | None = None,
    lock_stale_after_seconds: int = 7200,
) -> DataRefreshWorkflowRecord:
    """Refresh data, run dry-run signals, compare, and optionally publish."""
    started_at = datetime.now(UTC)
    ingest_artifact: IngestArtifactPaths | None = None
    scheduler_records: tuple[ScheduledRunRecord, ...] = ()
    comparison_path: Path | None = None
    status_path: Path | None = None
    lock_owner: str | None = None

    try:
        lock = (
            FileLock(
                path=lock_path,
                lock_name="dry-run-refresh",
                stale_after_seconds=lock_stale_after_seconds,
            )
            if lock_path is not None
            else None
        )
        if lock is not None:
            lock_owner = lock.acquire().owner

        try:
            if strategy != "momentum":
                raise ValueError("Only momentum is implemented right now.")

            request = IngestRequest(symbols=(symbol,), start=start, end=end)
            artifacts = ingest_market_bars(
                provider,
                request,
                raw_root=raw_dir,
                normalized_root=normalized_dir,
                validation_root=validation_dir,
                metadata_root=metadata_dir,
                validate=True,
                min_rows=min_rows,
            )
            ingest_artifact = _single_artifact(artifacts)
            if ingest_artifact.validation_passed is not True:
                raise ValueError(
                    "data refresh validation failed; dry-run signal was not run"
                )

            scheduler_records = _run_dry_run_signal_loop(
                data=Path(ingest_artifact.normalized_path),
                symbol=symbol,
                quantity=quantity,
                broker_name=broker_name,
                iterations=iterations,
                interval_seconds=interval_seconds,
                dry_run_output_dir=dry_run_output_dir,
                run_output_dir=run_output_dir,
            )
            failed_runs = [
                record
                for record in scheduler_records
                if record.status.value == "failed"
            ]
            if failed_runs:
                message = (
                    f"{len(failed_runs)} dry-run signal scheduler runs failed"
                )
                status = WorkflowRunStatus.FAILED
            else:
                comparison_path = _compare_latest_paper_and_dry_run(
                    paper_signal_dir=paper_signal_dir,
                    dry_run_output_dir=dry_run_output_dir,
                    comparison_output_path=comparison_output_path,
                )
                message = "data refreshed and dry-run workflow completed"
                status = WorkflowRunStatus.SUCCEEDED
        finally:
            if lock is not None:
                lock.release()

        if status == WorkflowRunStatus.SUCCEEDED:
            # Publish after releasing the workflow lock so dashboard health
            # reflects the finished run, not the in-progress lock we just held.
            status_path = _publish_dry_run_workflow_status(
                publish_status_path=publish_status_path,
                run_records_dir=health_run_records_dir or run_output_dir,
                signal_records_dir=paper_signal_dir,
                state_path=paper_state_path,
                logs_dir=logs_dir,
                comparison_report_path=comparison_path,
                lock_path=lock_path,
                lock_stale_after_seconds=lock_stale_after_seconds,
            )

        record = _build_record(
            status=status,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=message,
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
            workflow_name="dry-run-refresh",
            extra_artifact_paths=tuple(
                str(path)
                for path in (comparison_path, status_path)
                if path is not None
            ),
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        if status == WorkflowRunStatus.FAILED:
            raise WorkflowRunFailed(record)
        return record
    except WorkflowRunFailed:
        raise
    except Exception as exc:
        record = _build_record(
            status=WorkflowRunStatus.FAILED,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=str(exc),
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=run_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
            workflow_name="dry-run-refresh",
            extra_artifact_paths=tuple(
                str(path)
                for path in (comparison_path, status_path)
                if path is not None
            ),
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        raise WorkflowRunFailed(record) from exc


def run_alpaca_paper_refresh_workflow(
    *,
    provider: DataProvider,
    broker_client: LiveBrokerClient,
    safety_config: TradingSafetyConfig,
    symbol: str,
    start: str,
    end: str | None,
    raw_dir: Path,
    normalized_dir: Path,
    validation_dir: Path,
    metadata_dir: Path,
    workflow_output_dir: Path,
    strategy: str,
    quantity: int,
    min_rows: int,
    order_output_dir: Path,
    fill_output_dir: Path,
    snapshot_output_dir: Path,
    reconciliation_output_path: Path,
    cash_tolerance: float = 0.01,
    order_poll_attempts: int = 5,
    order_poll_interval_seconds: float = 1,
    lock_path: Path | None = None,
    lock_stale_after_seconds: int = 7200,
) -> DataRefreshWorkflowRecord:
    """Refresh validated data, submit one Alpaca paper signal, and reconcile.

    This workflow is intentionally finite. A scheduler or server wrapper can run
    it frequently later, while each invocation remains easy to inspect and
    retry from its durable artifacts.
    """
    started_at = datetime.now(UTC)
    ingest_artifact: IngestArtifactPaths | None = None
    scheduler_records: tuple[ScheduledRunRecord, ...] = ()
    extra_artifact_paths: tuple[str, ...] = ()
    alpaca_paper_outcome = _AlpacaPaperSignalRunOutcome()
    lock_owner: str | None = None

    try:
        lock = (
            FileLock(
                path=lock_path,
                lock_name="alpaca-paper-refresh",
                stale_after_seconds=lock_stale_after_seconds,
            )
            if lock_path is not None
            else None
        )
        if lock is not None:
            lock_owner = lock.acquire().owner

        try:
            if strategy != "momentum":
                raise ValueError("Only momentum is implemented right now.")
            if quantity < 1:
                raise ValueError("quantity must be at least 1")
            if cash_tolerance < 0:
                raise ValueError("cash_tolerance must be non-negative")
            if order_poll_attempts < 1:
                raise ValueError("order_poll_attempts must be at least 1")
            if order_poll_interval_seconds < 0:
                raise ValueError(
                    "order_poll_interval_seconds must be non-negative"
                )

            request = IngestRequest(symbols=(symbol,), start=start, end=end)
            artifacts = ingest_market_bars(
                provider,
                request,
                raw_root=raw_dir,
                normalized_root=normalized_dir,
                validation_root=validation_dir,
                metadata_root=metadata_dir,
                validate=True,
                min_rows=min_rows,
            )
            ingest_artifact = _single_artifact(artifacts)
            if ingest_artifact.validation_passed is not True:
                raise ValueError(
                    "data refresh validation failed; Alpaca paper signal "
                    "was not run"
                )

            try:
                alpaca_paper_outcome = _run_alpaca_paper_signal_once(
                    data=Path(ingest_artifact.normalized_path),
                    symbol=symbol,
                    quantity=quantity,
                    broker_client=broker_client,
                    safety_config=safety_config,
                    order_output_dir=order_output_dir,
                    fill_output_dir=fill_output_dir,
                    snapshot_output_dir=snapshot_output_dir,
                    reconciliation_output_path=reconciliation_output_path,
                    cash_tolerance=cash_tolerance,
                    order_poll_attempts=order_poll_attempts,
                    order_poll_interval_seconds=order_poll_interval_seconds,
                )
                extra_artifact_paths = alpaca_paper_outcome.artifact_paths
            except _AlpacaPaperSignalFailed as exc:
                alpaca_paper_outcome = exc.outcome
                extra_artifact_paths = exc.outcome.artifact_paths
                raise ValueError(str(exc)) from exc
            message = "data refreshed and Alpaca paper workflow completed"
            status = WorkflowRunStatus.SUCCEEDED
        finally:
            if lock is not None:
                lock.release()

        record = _build_record(
            status=status,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=message,
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=workflow_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
            workflow_name="alpaca-paper-refresh",
            extra_artifact_paths=extra_artifact_paths,
            alpaca_paper_outcome=alpaca_paper_outcome,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        return record
    except WorkflowRunFailed:
        raise
    except Exception as exc:
        record = _build_record(
            status=WorkflowRunStatus.FAILED,
            started_at=started_at,
            provider=provider.name,
            symbol=symbol,
            start=start,
            end=end,
            message=str(exc),
            ingest_artifact=ingest_artifact,
            scheduler_records=scheduler_records,
            run_output_dir=workflow_output_dir,
            lock_path=lock_path,
            lock_owner=lock_owner,
            workflow_name="alpaca-paper-refresh",
            extra_artifact_paths=extra_artifact_paths,
            alpaca_paper_outcome=alpaca_paper_outcome,
        )
        write_data_refresh_workflow_record(record, workflow_output_dir)
        raise WorkflowRunFailed(record) from exc


def write_data_refresh_workflow_record(
    record: DataRefreshWorkflowRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.workflow_id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def _run_paper_signal_loop(
    *,
    data: Path,
    symbol: str,
    quantity: int,
    initial_cash: float,
    initial_position_quantity: int,
    initial_position_price: float,
    iterations: int,
    interval_seconds: float,
    signal_output_dir: Path,
    state_path: Path,
    run_output_dir: Path,
) -> tuple[ScheduledRunRecord, ...]:
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
    strategy = MomentumStrategy()

    def task() -> ScheduledTaskResult:
        # The workflow has already refreshed and validated this normalized file.
        # Reloading inside each attempt matches the scheduler v1 behavior.
        prices = load_price_csv(data, symbol)
        record = execute_latest_signal(
            strategy=strategy,
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

    return runner.run_loop(
        task_name="paper-signal",
        task=task,
        iterations=iterations,
        interval_seconds=interval_seconds,
    )


def _run_dry_run_signal_loop(
    *,
    data: Path,
    symbol: str,
    quantity: int,
    broker_name: str,
    iterations: int,
    interval_seconds: float,
    dry_run_output_dir: Path,
    run_output_dir: Path,
) -> tuple[ScheduledRunRecord, ...]:
    runner = SchedulerRunner(output_dir=run_output_dir)
    strategy = MomentumStrategy()
    adapter = DryRunBrokerAdapter(broker_name=broker_name)
    check = evaluate_trading_safety(
        TradingSafetyConfig(mode=TradingMode.DRY_RUN)
    )

    def task() -> ScheduledTaskResult:
        # The workflow has already refreshed and validated this normalized file.
        prices = load_price_csv(data, symbol)
        decision, record = execute_latest_signal_dry_run(
            strategy=strategy,
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

    return runner.run_loop(
        task_name="dry-run-signal",
        task=task,
        iterations=iterations,
        interval_seconds=interval_seconds,
    )


def _run_alpaca_paper_signal_once(
    *,
    data: Path,
    symbol: str,
    quantity: int,
    broker_client: LiveBrokerClient,
    safety_config: TradingSafetyConfig,
    order_output_dir: Path,
    fill_output_dir: Path,
    snapshot_output_dir: Path,
    reconciliation_output_path: Path,
    cash_tolerance: float,
    order_poll_attempts: int,
    order_poll_interval_seconds: float,
) -> _AlpacaPaperSignalRunOutcome:
    strategy = MomentumStrategy()
    prices = load_price_csv(data, symbol)
    signals = strategy.generate_signals(prices)
    decision = decide_latest_signal(
        strategy_name=strategy.name,
        prices=prices,
        signals=signals,
    )
    safety_check = evaluate_trading_safety(safety_config)
    if not safety_check.allowed:
        raise ValueError(
            f"Alpaca paper safety check failed: {safety_check.reason}"
        )

    before_paths = _existing_json_paths(
        order_output_dir,
        fill_output_dir,
        snapshot_output_dir,
    )
    adapter = LiveBrokerAdapter(
        client=broker_client,
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )

    account_before_order = broker_client.account_snapshot()
    target_plan = plan_target_position_order(
        decision=decision,
        account=account_before_order,
        target_long_quantity=quantity,
    )
    request = target_plan.order_request
    broker_submission_attempted = request is not None
    broker_submission_skipped_reason: str | None = None
    if request is None:
        broker_submission_skipped_reason = (
            "latest strategy signal is hold"
            if decision.action == PaperSignalAction.HOLD
            else target_plan.reason
        )

    if request is not None:
        # Fail closed while another broker order is unsettled. The account
        # snapshot can still show cash or positions reserved by that order,
        # which would make a second local risk check incorrectly approve.
        if broker_client.has_open_orders():
            raise ValueError(
                "Alpaca paper order risk check failed: "
                "open broker order(s) must settle first"
            )
        _validate_live_order_notional(
            quantity=request.quantity,
            price=decision.market_price,
            max_order_notional=safety_config.max_order_notional,
        )
        risk = check_projected_order_risk(
            request,
            account=account_before_order,
            market_price=decision.market_price,
            short_policy=safety_config.short_selling_policy,
        )
        if not risk.approved:
            raise ValueError(
                "Alpaca paper order risk check failed: "
                f"{risk.reason or 'no rejection reason provided'}"
            )
        if opens_or_increases_short(request, account=account_before_order):
            availability = check_short_sale_availability(
                request,
                account=account_before_order,
                asset=broker_client.asset_trading_details(symbol),
            )
            if not availability.approved:
                raise ValueError(
                    "Alpaca paper order risk check failed: "
                    f"{availability.reason or 'no rejection reason provided'}"
                )

        order = adapter.submit_market_order(
            request,
            reference_price=decision.market_price,
            client_order_id=decision.idempotency_key,
            safety_check=safety_check,
        )
        if order.status == LiveOrderStatus.REJECTED:
            raise ValueError(
                "Alpaca paper order was rejected: "
                f"{order.rejection_reason or 'no rejection reason provided'}"
            )
        order = _refresh_order_until_terminal(
            adapter=adapter,
            order=order,
            attempts=order_poll_attempts,
            interval_seconds=order_poll_interval_seconds,
        )
        if order.status not in _TERMINAL_LIVE_ORDER_STATUSES:
            raise ValueError(
                "Alpaca paper order did not reach a terminal state before "
                "reconciliation"
            )
        if order.status != LiveOrderStatus.FILLED:
            raise ValueError(
                "Alpaca paper actionable order ended with status "
                f"{order.status.value}"
            )
    adapter.account_snapshot()

    report = reconcile_live_state(
        client=broker_client,
        order_records_dir=order_output_dir,
        fill_records_dir=fill_output_dir,
        snapshot_records_dir=snapshot_output_dir,
        cash_tolerance=cash_tolerance,
    )
    report_path = write_live_reconciliation_report(
        report,
        reconciliation_output_path,
    )
    extra_paths = (
        *_new_json_paths(order_output_dir, before_paths),
        *_new_json_paths(fill_output_dir, before_paths),
        *_new_json_paths(snapshot_output_dir, before_paths),
        str(report_path),
    )
    order_paths = _new_json_paths(order_output_dir, before_paths)
    fill_paths = _new_json_paths(fill_output_dir, before_paths)
    snapshot_paths = _new_json_paths(snapshot_output_dir, before_paths)
    outcome = _AlpacaPaperSignalRunOutcome(
        artifact_paths=extra_paths,
        latest_signal_action=decision.action.value,
        latest_signal_reason=decision.reason,
        latest_signal_market_price=decision.market_price,
        broker_submission_attempted=broker_submission_attempted,
        broker_submission_skipped_reason=broker_submission_skipped_reason,
        broker_position_quantity_before=target_plan.current_quantity,
        strategy_target_quantity=target_plan.target_quantity,
        planned_order_side=request.side.value if request is not None else None,
        planned_order_quantity=(
            request.quantity if request is not None else None
        ),
        order_artifact_paths=order_paths,
        fill_artifact_paths=fill_paths,
        snapshot_artifact_paths=snapshot_paths,
        reconciliation_report_path=str(report_path),
    )
    if not report.passed:
        raise _AlpacaPaperSignalFailed(
            "Alpaca paper reconciliation failed",
            outcome,
        )
    return outcome


_TERMINAL_LIVE_ORDER_STATUSES = {
    LiveOrderStatus.CANCELLED,
    LiveOrderStatus.FILLED,
    LiveOrderStatus.REJECTED,
}


def _refresh_order_until_terminal(
    *,
    adapter: LiveBrokerAdapter,
    order: LiveOrderRecord,
    attempts: int,
    interval_seconds: float,
) -> LiveOrderRecord:
    refreshed = order
    for attempt in range(attempts):
        if refreshed.status in _TERMINAL_LIVE_ORDER_STATUSES:
            return refreshed
        if attempt > 0 and interval_seconds > 0:
            sleep(interval_seconds)
        refreshed = adapter.refresh_order_record(refreshed)
    return refreshed


def _validate_live_order_notional(
    *,
    quantity: int,
    price: float,
    max_order_notional: float | None,
) -> None:
    if price <= 0:
        raise ValueError("price must be positive")
    notional = quantity * price
    if max_order_notional is not None and notional > max_order_notional:
        raise ValueError("order notional exceeds max_order_notional")


def _existing_json_paths(*directories: Path) -> set[Path]:
    paths: set[Path] = set()
    for directory in directories:
        paths.update(directory.glob("*.json"))
    return paths


def _new_json_paths(
    directory: Path,
    before_paths: set[Path],
) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(directory.glob("*.json"))
        if path not in before_paths
    )


def _compare_latest_paper_and_dry_run(
    *,
    paper_signal_dir: Path,
    dry_run_output_dir: Path,
    comparison_output_path: Path,
) -> Path | None:
    paper_signal_path = latest_json(paper_signal_dir)
    if paper_signal_path is None:
        # A brand-new dry-run deployment may not have paper records yet. In that
        # case the workflow can still prove refresh and dry-run execution work.
        return None
    dry_run_order_path = latest_json(dry_run_output_dir)
    report = compare_paper_signal_to_dry_run_order(
        paper_signal_path=paper_signal_path,
        dry_run_order_path=dry_run_order_path,
    )
    report_path = write_paper_dry_run_comparison_report(
        report,
        comparison_output_path,
    )
    if not report.passed:
        raise ValueError("paper-vs-dry-run comparison failed")
    return report_path


def _publish_dry_run_workflow_status(
    *,
    publish_status_path: Path | None,
    run_records_dir: Path,
    signal_records_dir: Path,
    state_path: Path,
    logs_dir: Path,
    comparison_report_path: Path | None,
    lock_path: Path | None,
    lock_stale_after_seconds: int,
) -> Path | None:
    if publish_status_path is None:
        return None

    report = build_health_report(
        run_records_dir=run_records_dir,
        signal_records_dir=signal_records_dir,
        state_path=state_path,
        logs_dir=logs_dir,
        lock_path=lock_path,
        lock_stale_after_seconds=lock_stale_after_seconds,
        reconcile_state=False,
        check_comparison=comparison_report_path is not None,
        comparison_report_path=comparison_report_path,
    )
    status = build_dashboard_health_status(report)
    return write_dashboard_health_status(status, publish_status_path)


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


def _single_artifact(
    artifacts: list[IngestArtifactPaths],
) -> IngestArtifactPaths:
    if len(artifacts) != 1:
        raise ValueError("paper signal refresh expects exactly one symbol")
    return artifacts[0]


def _build_record(
    *,
    status: WorkflowRunStatus,
    started_at: datetime,
    provider: str,
    symbol: str,
    start: str,
    end: str | None,
    message: str,
    ingest_artifact: IngestArtifactPaths | None,
    scheduler_records: tuple[ScheduledRunRecord, ...],
    run_output_dir: Path,
    lock_path: Path | None,
    lock_owner: str | None,
    workflow_name: str = "paper-signal-refresh",
    extra_artifact_paths: tuple[str, ...] = (),
    alpaca_paper_outcome: _AlpacaPaperSignalRunOutcome | None = None,
) -> DataRefreshWorkflowRecord:
    scheduler_run_paths = tuple(
        str(run_output_dir / f"{record.run_id}.json")
        for record in scheduler_records
    )
    artifact_paths = _artifact_paths(
        ingest_artifact=ingest_artifact,
        scheduler_run_paths=scheduler_run_paths,
        scheduler_records=scheduler_records,
        extra_artifact_paths=extra_artifact_paths,
    )
    return DataRefreshWorkflowRecord(
        workflow_name=workflow_name,
        status=status,
        started_at=started_at,
        provider=provider,
        symbol=symbol,
        request_start=start,
        request_end=end,
        message=message,
        raw_path=ingest_artifact.raw_path if ingest_artifact else None,
        normalized_path=(
            ingest_artifact.normalized_path if ingest_artifact else None
        ),
        validation_report_path=(
            ingest_artifact.validation_report_path
            if ingest_artifact
            else None
        ),
        metadata_path=(
            ingest_artifact.metadata_path if ingest_artifact else None
        ),
        lock_path=str(lock_path) if lock_path is not None else None,
        lock_owner=lock_owner,
        scheduler_run_paths=scheduler_run_paths,
        artifact_paths=artifact_paths,
        latest_signal_action=(
            alpaca_paper_outcome.latest_signal_action
            if alpaca_paper_outcome is not None
            else None
        ),
        latest_signal_reason=(
            alpaca_paper_outcome.latest_signal_reason
            if alpaca_paper_outcome is not None
            else None
        ),
        latest_signal_market_price=(
            alpaca_paper_outcome.latest_signal_market_price
            if alpaca_paper_outcome is not None
            else None
        ),
        broker_submission_attempted=(
            alpaca_paper_outcome.broker_submission_attempted
            if alpaca_paper_outcome is not None
            else None
        ),
        broker_submission_skipped_reason=(
            alpaca_paper_outcome.broker_submission_skipped_reason
            if alpaca_paper_outcome is not None
            else None
        ),
        broker_position_quantity_before=(
            alpaca_paper_outcome.broker_position_quantity_before
            if alpaca_paper_outcome is not None
            else None
        ),
        strategy_target_quantity=(
            alpaca_paper_outcome.strategy_target_quantity
            if alpaca_paper_outcome is not None
            else None
        ),
        planned_order_side=(
            alpaca_paper_outcome.planned_order_side
            if alpaca_paper_outcome is not None
            else None
        ),
        planned_order_quantity=(
            alpaca_paper_outcome.planned_order_quantity
            if alpaca_paper_outcome is not None
            else None
        ),
        order_artifact_paths=(
            alpaca_paper_outcome.order_artifact_paths
            if alpaca_paper_outcome is not None
            else ()
        ),
        fill_artifact_paths=(
            alpaca_paper_outcome.fill_artifact_paths
            if alpaca_paper_outcome is not None
            else ()
        ),
        snapshot_artifact_paths=(
            alpaca_paper_outcome.snapshot_artifact_paths
            if alpaca_paper_outcome is not None
            else ()
        ),
        reconciliation_report_path=(
            alpaca_paper_outcome.reconciliation_report_path
            if alpaca_paper_outcome is not None
            else None
        ),
    )


def _artifact_paths(
    *,
    ingest_artifact: IngestArtifactPaths | None,
    scheduler_run_paths: tuple[str, ...],
    scheduler_records: tuple[ScheduledRunRecord, ...],
    extra_artifact_paths: tuple[str, ...] = (),
) -> tuple[str, ...]:
    paths: list[str] = []
    if ingest_artifact is not None:
        paths.extend(
            path
            for path in (
                ingest_artifact.raw_path,
                ingest_artifact.normalized_path,
                ingest_artifact.validation_report_path,
                ingest_artifact.metadata_path,
            )
            if path is not None
        )
    paths.extend(scheduler_run_paths)
    for record in scheduler_records:
        paths.extend(record.artifact_paths)
    paths.extend(extra_artifact_paths)
    return tuple(paths)
