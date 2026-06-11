from pathlib import Path

from quant.execution.live_broker import LiveBrokerClient
from quant.models.execution import (
    Fill,
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationDifference,
    LiveReconciliationObservation,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderSide,
    PaperBrokerState,
    PaperSignalAction,
    PaperSignalRecord,
    PaperStateDifference,
    PaperStateReconciliationReport,
    Position,
)


def reconcile_paper_state(
    *,
    state: PaperBrokerState,
    state_path: Path,
    signal_records_dir: Path,
    initial_cash: float,
    initial_positions: tuple[Position, ...] = (),
    cash_tolerance: float = 0.01,
) -> PaperStateReconciliationReport:
    """Replay paper signal records and compare them with persisted state."""
    expected_cash = initial_cash
    expected_positions = {
        position.symbol: position for position in initial_positions
    }
    expected_signal_keys: set[str] = set()
    filled_trade_count = 0

    records = load_paper_signal_records(signal_records_dir)
    for record in records:
        if _records_processed_signal_key(record):
            expected_signal_keys.add(record.decision.idempotency_key)
        if record.trade is not None and record.trade.fill is not None:
            expected_cash, expected_positions = _apply_fill(
                record.trade.fill,
                cash=expected_cash,
                positions=expected_positions,
            )
            filled_trade_count += 1

    expected_state = PaperBrokerState(
        cash=expected_cash,
        positions=tuple(
            sorted(expected_positions.values(), key=lambda item: item.symbol)
        ),
        processed_signal_keys=tuple(sorted(expected_signal_keys)),
    )
    actual_positions = tuple(
        sorted(state.positions, key=lambda item: item.symbol)
    )
    actual_signal_keys = tuple(sorted(state.processed_signal_keys))
    actual_state = PaperBrokerState(
        cash=state.cash,
        positions=actual_positions,
        processed_signal_keys=actual_signal_keys,
    )
    differences = _compare_states(
        expected=expected_state,
        actual=actual_state,
        cash_tolerance=cash_tolerance,
    )
    return PaperStateReconciliationReport(
        state_path=str(state_path),
        signal_records_dir=str(signal_records_dir),
        signal_record_count=len(records),
        filled_trade_count=filled_trade_count,
        expected_cash=expected_state.cash,
        actual_cash=actual_state.cash,
        expected_positions=expected_state.positions,
        actual_positions=actual_state.positions,
        expected_processed_signal_keys=expected_state.processed_signal_keys,
        actual_processed_signal_keys=actual_state.processed_signal_keys,
        differences=tuple(differences),
    )


def load_paper_signal_records(
    signal_records_dir: Path,
) -> tuple[PaperSignalRecord, ...]:
    records = []
    for path in sorted(signal_records_dir.glob("*.json")):
        records.append(PaperSignalRecord.model_validate_json(path.read_text()))
    return tuple(sorted(records, key=_signal_record_sort_key))


def write_paper_state_reconciliation_report(
    report: PaperStateReconciliationReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n")
    return path


def reconcile_live_state(
    *,
    client: LiveBrokerClient,
    order_records_dir: Path,
    fill_records_dir: Path,
    snapshot_records_dir: Path,
    cash_tolerance: float = 0.01,
) -> LiveReconciliationReport:
    """Compare local live artifacts against broker-client truth.

    This is intentionally read-only. It never submits, cancels, or mutates
    broker state; it only asks the client for current truth and reports drift.
    """
    if cash_tolerance < 0:
        raise ValueError("cash_tolerance must be non-negative")

    local_orders = load_live_order_records(order_records_dir)
    local_open_orders = _open_live_orders(local_orders)
    local_fills = load_live_fill_records(fill_records_dir)
    local_snapshot = latest_live_account_snapshot(snapshot_records_dir)
    broker_open_orders = client.open_orders()
    broker_fills = client.fills()
    broker_snapshot = client.account_snapshot()

    differences: list[LiveReconciliationDifference] = []
    differences.extend(
        _compare_live_open_orders(
            local=local_open_orders,
            broker=broker_open_orders,
        )
    )
    differences.extend(
        _compare_live_fills(local=local_fills, broker=broker_fills)
    )
    snapshot_differences, observations = _compare_live_snapshot(
        local=local_snapshot,
        broker=broker_snapshot,
        tolerance=cash_tolerance,
    )
    differences.extend(snapshot_differences)

    return LiveReconciliationReport(
        broker_name=broker_snapshot.broker_name,
        account_id=broker_snapshot.account_id,
        broker_environment=broker_snapshot.broker_environment,
        local_order_count=len(local_open_orders),
        broker_order_count=len(broker_open_orders),
        local_fill_count=len(local_fills),
        broker_fill_count=len(broker_fills),
        local_position_count=(
            len(local_snapshot.positions) if local_snapshot is not None else 0
        ),
        broker_position_count=len(broker_snapshot.positions),
        status=(
            LiveReconciliationStatus.PASSED
            if not differences
            else LiveReconciliationStatus.FAILED
        ),
        differences=tuple(differences),
        observations=tuple(observations),
    )


def load_live_order_records(
    order_records_dir: Path,
) -> tuple[LiveOrderRecord, ...]:
    records = []
    for path in sorted(order_records_dir.glob("*.json")):
        records.append(LiveOrderRecord.model_validate_json(path.read_text()))
    return tuple(sorted(records, key=lambda record: record.recorded_at))


def load_live_fill_records(
    fill_records_dir: Path,
) -> tuple[LiveFillRecord, ...]:
    records = []
    for path in sorted(fill_records_dir.glob("*.json")):
        records.append(LiveFillRecord.model_validate_json(path.read_text()))
    return tuple(sorted(records, key=lambda record: record.recorded_at))


def latest_live_account_snapshot(
    snapshot_records_dir: Path,
) -> LiveAccountSnapshot | None:
    paths = sorted(
        snapshot_records_dir.glob("*.json"),
        key=lambda path: path.stat().st_mtime,
    )
    if not paths:
        return None
    return LiveAccountSnapshot.model_validate_json(paths[-1].read_text())


def _records_processed_signal_key(record: PaperSignalRecord) -> bool:
    return (
        record.decision.action != PaperSignalAction.HOLD
        and not record.skipped
    )


def _open_live_orders(
    records: tuple[LiveOrderRecord, ...],
) -> tuple[LiveOrderRecord, ...]:
    terminal = {
        LiveOrderStatus.CANCELLED,
        LiveOrderStatus.FILLED,
        LiveOrderStatus.REJECTED,
    }
    return tuple(record for record in records if record.status not in terminal)


def _compare_live_open_orders(
    *,
    local: tuple[LiveOrderRecord, ...],
    broker: tuple[LiveOrderRecord, ...],
) -> list[LiveReconciliationDifference]:
    differences: list[LiveReconciliationDifference] = []
    local_by_key = {_live_order_key(record): record for record in local}
    broker_by_key = {_live_order_key(record): record for record in broker}
    keys = sorted(local_by_key.keys() | broker_by_key.keys())
    for key in keys:
        local_record = local_by_key.get(key)
        broker_record = broker_by_key.get(key)
        if local_record is None or broker_record is None:
            differences.append(
                LiveReconciliationDifference(
                    field=f"open_orders.{key}",
                    local_value=str(local_record),
                    broker_value=str(broker_record),
                    message="open order presence differs",
                )
            )
            continue
        if local_record.status != broker_record.status:
            differences.append(
                LiveReconciliationDifference(
                    field=f"open_orders.{key}.status",
                    local_value=local_record.status.value,
                    broker_value=broker_record.status.value,
                    message="open order status differs",
                )
            )
    return differences


def _compare_live_fills(
    *,
    local: tuple[LiveFillRecord, ...],
    broker: tuple[LiveFillRecord, ...],
) -> list[LiveReconciliationDifference]:
    differences: list[LiveReconciliationDifference] = []
    local_by_key = {_live_fill_key(record): record for record in local}
    broker_by_key = {_live_fill_key(record): record for record in broker}
    keys = sorted(local_by_key.keys() | broker_by_key.keys())
    for key in keys:
        local_fill = local_by_key.get(key)
        broker_fill = broker_by_key.get(key)
        if local_fill is None or broker_fill is None:
            differences.append(
                LiveReconciliationDifference(
                    field=f"fills.{key}",
                    local_value=str(local_fill),
                    broker_value=str(broker_fill),
                    message="fill presence differs",
                )
            )
            continue
        differences.extend(
            _compare_live_fill_values(
                key=key,
                local=local_fill,
                broker=broker_fill,
            )
        )
    return differences


def _compare_live_fill_values(
    *,
    key: str,
    local: LiveFillRecord,
    broker: LiveFillRecord,
) -> list[LiveReconciliationDifference]:
    differences: list[LiveReconciliationDifference] = []
    for field in ("symbol", "side", "quantity"):
        local_value = getattr(local, field)
        broker_value = getattr(broker, field)
        if local_value != broker_value:
            differences.append(
                LiveReconciliationDifference(
                    field=f"fills.{key}.{field}",
                    local_value=str(local_value),
                    broker_value=str(broker_value),
                    message="fill value differs",
                )
            )
    for field in ("price", "commission"):
        local_value = getattr(local, field)
        broker_value = getattr(broker, field)
        if abs(local_value - broker_value) > 0.01:
            differences.append(
                LiveReconciliationDifference(
                    field=f"fills.{key}.{field}",
                    local_value=f"{local_value:.6f}",
                    broker_value=f"{broker_value:.6f}",
                    message="fill numeric value differs",
                )
            )
    return differences


def _compare_live_snapshot(
    *,
    local: LiveAccountSnapshot | None,
    broker: LiveAccountSnapshot,
    tolerance: float,
) -> tuple[
    list[LiveReconciliationDifference],
    list[LiveReconciliationObservation],
]:
    if local is None:
        return (
            [
                LiveReconciliationDifference(
                    field="account_snapshot",
                    local_value="missing",
                    broker_value=broker.id,
                    message="local account snapshot is missing",
                )
            ],
            [],
        )

    differences: list[LiveReconciliationDifference] = []
    observations: list[LiveReconciliationObservation] = []
    if abs(local.cash - broker.cash) > tolerance:
        differences.append(
            LiveReconciliationDifference(
                field="cash",
                local_value=f"{local.cash:.6f}",
                broker_value=f"{broker.cash:.6f}",
                message="account cash differs",
            )
        )
    _observe_live_numeric_value(
        field="buying_power",
        local_value=local.buying_power,
        broker_value=broker.buying_power,
        tolerance=tolerance,
        observations=observations,
    )
    position_differences, position_observations = _compare_live_positions(
        local=local.positions,
        broker=broker.positions,
        tolerance=tolerance,
    )
    differences.extend(position_differences)
    observations.extend(position_observations)
    return differences, observations


def _compare_live_positions(
    *,
    local: tuple[Position, ...],
    broker: tuple[Position, ...],
    tolerance: float,
) -> tuple[
    list[LiveReconciliationDifference],
    list[LiveReconciliationObservation],
]:
    differences: list[LiveReconciliationDifference] = []
    observations: list[LiveReconciliationObservation] = []
    local_by_symbol = {position.symbol: position for position in local}
    broker_by_symbol = {position.symbol: position for position in broker}
    symbols = sorted(local_by_symbol.keys() | broker_by_symbol.keys())
    for symbol in symbols:
        local_position = local_by_symbol.get(symbol)
        broker_position = broker_by_symbol.get(symbol)
        if local_position is None or broker_position is None:
            differences.append(
                LiveReconciliationDifference(
                    field=f"positions.{symbol}",
                    local_value=str(local_position),
                    broker_value=str(broker_position),
                    message="position presence differs",
                )
            )
            continue
        position_differences, position_observations = (
            _compare_live_position_values(
                symbol=symbol,
                local=local_position,
                broker=broker_position,
                tolerance=tolerance,
            )
        )
        differences.extend(position_differences)
        observations.extend(position_observations)
    return differences, observations


def _compare_live_position_values(
    *,
    symbol: str,
    local: Position,
    broker: Position,
    tolerance: float,
) -> tuple[
    list[LiveReconciliationDifference],
    list[LiveReconciliationObservation],
]:
    differences: list[LiveReconciliationDifference] = []
    observations: list[LiveReconciliationObservation] = []
    if local.quantity != broker.quantity:
        differences.append(
            LiveReconciliationDifference(
                field=f"positions.{symbol}.quantity",
                local_value=str(local.quantity),
                broker_value=str(broker.quantity),
                message="position quantity differs",
            )
        )
    if abs(local.average_price - broker.average_price) > tolerance:
        differences.append(
            LiveReconciliationDifference(
                field=f"positions.{symbol}.average_price",
                local_value=f"{local.average_price:.6f}",
                broker_value=f"{broker.average_price:.6f}",
                message="position average price differs",
            )
        )
    _observe_live_numeric_value(
        field=f"positions.{symbol}.last_price",
        local_value=local.last_price,
        broker_value=broker.last_price,
        tolerance=tolerance,
        observations=observations,
    )
    return differences, observations


def _observe_live_numeric_value(
    *,
    field: str,
    local_value: float,
    broker_value: float,
    tolerance: float,
    observations: list[LiveReconciliationObservation],
) -> None:
    if abs(local_value - broker_value) <= tolerance:
        return
    observations.append(
        LiveReconciliationObservation(
            field=field,
            local_value=f"{local_value:.6f}",
            broker_value=f"{broker_value:.6f}",
            message="volatile market-derived value changed between snapshots",
        )
    )


def _live_order_key(record: LiveOrderRecord) -> str:
    return record.broker_order_id or record.client_order_id


def _live_fill_key(record: LiveFillRecord) -> str:
    return (
        record.broker_execution_id
        or f"{record.broker_order_id}:{record.symbol}:{record.quantity}"
    )


def _signal_record_sort_key(
    record: PaperSignalRecord,
) -> tuple[str, str, str]:
    created_at = ""
    if record.trade is not None:
        created_at = record.trade.order.created_at.isoformat()
    return (
        record.decision.signal_date,
        created_at,
        record.decision.idempotency_key,
    )


def _apply_fill(
    fill: Fill,
    *,
    cash: float,
    positions: dict[str, Position],
) -> tuple[float, dict[str, Position]]:
    updated_positions = dict(positions)
    if fill.side == OrderSide.BUY:
        cash -= fill.notional
        updated_positions[fill.symbol] = _apply_buy(
            updated_positions.get(fill.symbol), fill
        )
    else:
        cash += fill.notional
        updated = _apply_sell(updated_positions[fill.symbol], fill)
        if updated.quantity == 0:
            del updated_positions[fill.symbol]
        else:
            updated_positions[fill.symbol] = updated
    return cash, updated_positions


def _apply_buy(position: Position | None, fill: Fill) -> Position:
    if position is None:
        return Position(
            symbol=fill.symbol,
            quantity=fill.quantity,
            average_price=fill.price,
            last_price=fill.price,
        )

    total_quantity = position.quantity + fill.quantity
    average_price = (
        position.average_price * position.quantity + fill.notional
    ) / total_quantity
    return Position(
        symbol=position.symbol,
        quantity=total_quantity,
        average_price=average_price,
        last_price=fill.price,
    )


def _apply_sell(position: Position, fill: Fill) -> Position:
    return Position(
        symbol=position.symbol,
        quantity=position.quantity - fill.quantity,
        average_price=position.average_price,
        last_price=fill.price,
    )


def _compare_states(
    *,
    expected: PaperBrokerState,
    actual: PaperBrokerState,
    cash_tolerance: float,
) -> list[PaperStateDifference]:
    differences: list[PaperStateDifference] = []
    if abs(expected.cash - actual.cash) > cash_tolerance:
        differences.append(
            PaperStateDifference(
                field="cash",
                expected=f"{expected.cash:.6f}",
                actual=f"{actual.cash:.6f}",
                message="persisted cash does not match replayed cash",
            )
        )

    differences.extend(
        _compare_positions(
            expected=expected.positions,
            actual=actual.positions,
            cash_tolerance=cash_tolerance,
        )
    )
    if expected.processed_signal_keys != actual.processed_signal_keys:
        differences.append(
            PaperStateDifference(
                field="processed_signal_keys",
                expected=",".join(expected.processed_signal_keys),
                actual=",".join(actual.processed_signal_keys),
                message="processed signal keys do not match audit records",
            )
        )
    return differences


def _compare_positions(
    *,
    expected: tuple[Position, ...],
    actual: tuple[Position, ...],
    cash_tolerance: float,
) -> list[PaperStateDifference]:
    differences: list[PaperStateDifference] = []
    expected_by_symbol = {position.symbol: position for position in expected}
    actual_by_symbol = {position.symbol: position for position in actual}
    symbols = sorted(expected_by_symbol.keys() | actual_by_symbol.keys())

    for symbol in symbols:
        expected_position = expected_by_symbol.get(symbol)
        actual_position = actual_by_symbol.get(symbol)
        if expected_position is None or actual_position is None:
            differences.append(
                PaperStateDifference(
                    field=f"positions.{symbol}",
                    expected=str(expected_position),
                    actual=str(actual_position),
                    message="position presence differs",
                )
            )
            continue
        differences.extend(
            _compare_position_values(
                symbol=symbol,
                expected=expected_position,
                actual=actual_position,
                tolerance=cash_tolerance,
            )
        )
    return differences


def _compare_position_values(
    *,
    symbol: str,
    expected: Position,
    actual: Position,
    tolerance: float,
) -> list[PaperStateDifference]:
    differences: list[PaperStateDifference] = []
    if expected.quantity != actual.quantity:
        differences.append(
            _position_difference(
                symbol,
                "quantity",
                expected.quantity,
                actual.quantity,
            )
        )
    for field in ("average_price", "last_price"):
        expected_value = getattr(expected, field)
        actual_value = getattr(actual, field)
        if abs(expected_value - actual_value) > tolerance:
            differences.append(
                _position_difference(
                    symbol,
                    field,
                    expected_value,
                    actual_value,
                )
            )
    return differences


def _position_difference(
    symbol: str,
    field: str,
    expected: object,
    actual: object,
) -> PaperStateDifference:
    return PaperStateDifference(
        field=f"positions.{symbol}.{field}",
        expected=str(expected),
        actual=str(actual),
        message="position value does not match replayed state",
    )
