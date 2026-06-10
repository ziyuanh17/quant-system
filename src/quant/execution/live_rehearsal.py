from pathlib import Path
from time import sleep

from quant.execution.artifacts import (
    write_live_reconciliation_report,
    write_live_rehearsal_result,
)
from quant.execution.live_broker import LiveBrokerAdapter, LiveBrokerClient
from quant.execution.reconciliation import (
    load_live_order_records,
    reconcile_live_state,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveOrderRecord,
    LiveOrderStatus,
    LiveRehearsalResult,
    LiveRehearsalStatus,
    OrderRequest,
    OrderSide,
    TradingSafetyCheck,
)

ALPACA_PAPER_REHEARSAL_CONFIRMATION = "CONFIRM_ALPACA_PAPER_REHEARSAL_ORDER"


class LiveRehearsalBlockedError(RuntimeError):
    """Raised before submission when a rehearsal invariant does not hold."""


def run_alpaca_paper_order_rehearsal(
    *,
    client: LiveBrokerClient,
    safety_check: TradingSafetyCheck,
    symbol: str,
    reference_price: float,
    client_order_id: str,
    protected_positions: dict[str, int],
    confirmation: str,
    order_output_dir: Path,
    fill_output_dir: Path,
    snapshot_output_dir: Path,
    reconciliation_output_path: Path,
    rehearsal_output_dir: Path,
    max_order_notional: float | None,
    order_poll_attempts: int = 5,
    order_poll_interval_seconds: float = 1,
    cash_tolerance: float = 0.01,
) -> LiveRehearsalResult:
    """Submit exactly one isolated paper buy after strict invariant checks."""
    symbol = symbol.strip().upper()
    protected_positions = _normalize_protected_positions(protected_positions)
    _validate_rehearsal_inputs(
        symbol=symbol,
        reference_price=reference_price,
        client_order_id=client_order_id,
        protected_positions=protected_positions,
        confirmation=confirmation,
        max_order_notional=max_order_notional,
        order_poll_attempts=order_poll_attempts,
        order_poll_interval_seconds=order_poll_interval_seconds,
    )
    if client.has_open_orders():
        raise LiveRehearsalBlockedError("broker has open order(s)")
    if any(
        record.client_order_id == client_order_id
        for record in load_live_order_records(order_output_dir)
    ):
        raise LiveRehearsalBlockedError(
            "client order ID already exists locally"
        )

    before_paths = _existing_json_paths(
        order_output_dir,
        fill_output_dir,
        snapshot_output_dir,
    )
    adapter = LiveBrokerAdapter(
        client=client,
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )
    before = adapter.account_snapshot()
    if before.broker_environment != "paper":
        raise LiveRehearsalBlockedError(
            "Alpaca paper rehearsal requires a paper broker environment"
        )
    _validate_pre_submission_snapshot(
        snapshot=before,
        symbol=symbol,
        protected_positions=protected_positions,
    )
    asset = client.asset_trading_details(symbol)
    if not asset.tradable:
        raise LiveRehearsalBlockedError(
            f"rehearsal symbol {symbol} is not tradable"
        )
    if before.buying_power < reference_price:
        raise LiveRehearsalBlockedError("insufficient buying power")

    order = adapter.submit_market_order(
        OrderRequest(symbol=symbol, side=OrderSide.BUY, quantity=1),
        reference_price=reference_price,
        client_order_id=client_order_id,
        safety_check=safety_check,
    )
    order = _refresh_order_until_terminal(
        adapter=adapter,
        order=order,
        attempts=order_poll_attempts,
        interval_seconds=order_poll_interval_seconds,
    )
    failure_reasons: list[str] = []
    if order.status != LiveOrderStatus.FILLED:
        failure_reasons.append(
            f"order finished {order.status.value} instead of filled"
        )

    # Once submission has happened, never issue an automatic cleanup order.
    # Capture current truth and preserve every detected mismatch as evidence.
    after = adapter.account_snapshot()
    protected_after = _observed_protected_positions(
        after,
        protected_positions,
    )
    if protected_after != protected_positions:
        failure_reasons.append("protected positions changed after rehearsal")
    rehearsal_quantity_after = _position_quantity(after, symbol)
    if rehearsal_quantity_after != 1:
        failure_reasons.append(
            f"rehearsal symbol {symbol} expected 1 but observed "
            f"{rehearsal_quantity_after}"
        )

    report = reconcile_live_state(
        client=client,
        order_records_dir=order_output_dir,
        fill_records_dir=fill_output_dir,
        snapshot_records_dir=snapshot_output_dir,
        cash_tolerance=cash_tolerance,
    )
    report_path = write_live_reconciliation_report(
        report,
        reconciliation_output_path,
    )
    if not report.passed:
        failure_reasons.append("rehearsal reconciliation failed")

    result = LiveRehearsalResult(
        status=(
            LiveRehearsalStatus.FAILED
            if failure_reasons
            else LiveRehearsalStatus.PASSED
        ),
        client_order_id=client_order_id,
        symbol=symbol,
        quantity=1,
        reference_price=reference_price,
        protected_positions_expected=protected_positions,
        protected_positions_before=_observed_protected_positions(
            before,
            protected_positions,
        ),
        protected_positions_after=protected_after,
        rehearsal_symbol_quantity_before=_position_quantity(before, symbol),
        rehearsal_symbol_quantity_after=rehearsal_quantity_after,
        asset_tradable=asset.tradable,
        order_status=order.status,
        order_artifact_paths=_new_json_paths(order_output_dir, before_paths),
        fill_artifact_paths=_new_json_paths(fill_output_dir, before_paths),
        snapshot_artifact_paths=_new_json_paths(
            snapshot_output_dir,
            before_paths,
        ),
        reconciliation_path=str(report_path),
        reconciliation_passed=report.passed,
        failure_reason=(
            "; ".join(failure_reasons) if failure_reasons else None
        ),
    )
    write_live_rehearsal_result(result, rehearsal_output_dir)
    return result


def _validate_rehearsal_inputs(
    *,
    symbol: str,
    reference_price: float,
    client_order_id: str,
    protected_positions: dict[str, int],
    confirmation: str,
    max_order_notional: float | None,
    order_poll_attempts: int,
    order_poll_interval_seconds: float,
) -> None:
    if confirmation != ALPACA_PAPER_REHEARSAL_CONFIRMATION:
        raise LiveRehearsalBlockedError("rehearsal confirmation is missing")
    if not symbol:
        raise LiveRehearsalBlockedError("rehearsal symbol is required")
    if not protected_positions:
        raise LiveRehearsalBlockedError(
            "at least one protected position is required"
        )
    if symbol in protected_positions:
        raise LiveRehearsalBlockedError(
            "rehearsal symbol cannot be a protected symbol"
        )
    if reference_price <= 0:
        raise LiveRehearsalBlockedError("reference price must be positive")
    if max_order_notional is None or reference_price > max_order_notional:
        raise LiveRehearsalBlockedError(
            "rehearsal order exceeds max order notional"
        )
    if not client_order_id:
        raise LiveRehearsalBlockedError("client order ID is required")
    if order_poll_attempts < 1:
        raise LiveRehearsalBlockedError(
            "order poll attempts must be at least 1"
        )
    if order_poll_interval_seconds < 0:
        raise LiveRehearsalBlockedError(
            "order poll interval must be non-negative"
        )


def _normalize_protected_positions(
    protected_positions: dict[str, int],
) -> dict[str, int]:
    normalized: dict[str, int] = {}
    for symbol, quantity in protected_positions.items():
        normalized_symbol = symbol.strip().upper()
        if not normalized_symbol:
            raise LiveRehearsalBlockedError(
                "protected position symbol is required"
            )
        if normalized_symbol in normalized:
            raise LiveRehearsalBlockedError(
                f"duplicate protected position: {normalized_symbol}"
            )
        normalized[normalized_symbol] = quantity
    return normalized


def _validate_pre_submission_snapshot(
    *,
    snapshot: LiveAccountSnapshot,
    symbol: str,
    protected_positions: dict[str, int],
) -> None:
    observed = _observed_protected_positions(snapshot, protected_positions)
    for protected_symbol, expected in protected_positions.items():
        actual = observed[protected_symbol]
        if actual != expected:
            raise LiveRehearsalBlockedError(
                f"protected position {protected_symbol} expected {expected} "
                f"but observed {actual}"
            )
    if _position_quantity(snapshot, symbol) != 0:
        raise LiveRehearsalBlockedError(
            f"rehearsal symbol {symbol} already has a position"
        )


def _observed_protected_positions(
    snapshot: LiveAccountSnapshot,
    protected_positions: dict[str, int],
) -> dict[str, int]:
    return {
        symbol: _position_quantity(snapshot, symbol)
        for symbol in protected_positions
    }


def _position_quantity(snapshot: LiveAccountSnapshot, symbol: str) -> int:
    return next(
        (
            position.quantity
            for position in snapshot.positions
            if position.symbol == symbol
        ),
        0,
    )


_TERMINAL_ORDER_STATUSES = {
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
        if refreshed.status in _TERMINAL_ORDER_STATUSES:
            return refreshed
        if attempt > 0 and interval_seconds > 0:
            sleep(interval_seconds)
        refreshed = adapter.refresh_order_record(refreshed)
    return refreshed


def _existing_json_paths(*directories: Path) -> set[Path]:
    return {
        path for directory in directories for path in directory.glob("*.json")
    }


def _new_json_paths(
    directory: Path, before_paths: set[Path]
) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(directory.glob("*.json"))
        if path not in before_paths
    )
