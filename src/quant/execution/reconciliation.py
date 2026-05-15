from pathlib import Path

from quant.models.execution import (
    Fill,
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


def _records_processed_signal_key(record: PaperSignalRecord) -> bool:
    return (
        record.decision.action != PaperSignalAction.HOLD
        and not record.skipped
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
