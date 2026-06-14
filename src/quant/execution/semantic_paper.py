"""Implement durable live-shaped local semantic paper trading."""

import os
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from quant.execution.live_broker import LiveBrokerAdapter
from quant.models.execution import (
    AssetTradingDetails,
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    Position,
    SemanticPaperBrokerState,
    TradingMode,
    TradingSafetyCheck,
)
from quant.operations import FileLock

SEMANTIC_PAPER_BROKER_NAME = "semantic-paper"
SEMANTIC_PAPER_ACCOUNT_ID = "local-semantic-paper"
SEMANTIC_PAPER_ENVIRONMENT = "local-paper"


class SemanticPaperBrokerClient:
    """Durable no-network broker supporting signed semantic targets."""

    def __init__(
        self,
        *,
        state_path: Path,
        initial_cash: float,
        initial_positions: tuple[Position, ...] = (),
        broker_name: str = SEMANTIC_PAPER_BROKER_NAME,
        account_id: str = SEMANTIC_PAPER_ACCOUNT_ID,
        broker_environment: str = SEMANTIC_PAPER_ENVIRONMENT,
    ) -> None:
        if initial_cash < 0:
            raise ValueError("initial_cash must be non-negative")
        self._state_path = state_path
        self._lock_path = state_path.with_name(f"{state_path.name}.lock")
        self._initial_state = SemanticPaperBrokerState(
            broker_name=broker_name,
            account_id=account_id,
            broker_environment=broker_environment,
            cash=initial_cash,
            positions=initial_positions,
        )
        with self._lock():
            if state_path.exists():
                self._require_identity(self._load_state())
            else:
                self._save_state(self._initial_state)

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        _require_paper_safety(safety_check)
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        with self._lock():
            state = self._load_state()
            self._require_identity(state)
            existing = tuple(
                order
                for order in state.orders
                if order.client_order_id == client_order_id
            )
            if existing:
                if len(existing) != 1:
                    raise ValueError("client order ID maps to multiple orders")
                if existing[0].request != request:
                    raise ValueError(
                        "client order ID was reused for another order"
                    )
                return existing[0]

            order_sequence = state.order_sequence + 1
            broker_order_id = f"semantic-paper-order-{order_sequence}"
            rejection_reason = _rejection_reason(
                request,
                cash=state.cash,
                reference_price=reference_price,
            )
            status = (
                LiveOrderStatus.REJECTED
                if rejection_reason is not None
                else LiveOrderStatus.FILLED
            )
            order = LiveOrderRecord(
                client_order_id=client_order_id,
                broker_order_id=broker_order_id,
                broker_name=state.broker_name,
                account_id=state.account_id,
                broker_environment=state.broker_environment,
                request=request,
                reference_price=reference_price,
                notional=request.quantity * reference_price,
                safety_check=safety_check,
                status=status,
                rejection_reason=rejection_reason,
                raw_response_ref=f"semantic-paper:order:{broker_order_id}",
            )
            fills = state.fills
            positions = state.positions
            cash = state.cash
            execution_sequence = state.execution_sequence
            if status == LiveOrderStatus.FILLED:
                execution_sequence += 1
                fill = LiveFillRecord(
                    order_record_id=order.id,
                    client_order_id=client_order_id,
                    broker_order_id=broker_order_id,
                    broker_execution_id=(
                        f"semantic-paper-exec-{execution_sequence}"
                    ),
                    broker_name=state.broker_name,
                    account_id=state.account_id,
                    broker_environment=state.broker_environment,
                    symbol=request.symbol,
                    side=request.side,
                    quantity=request.quantity,
                    price=reference_price,
                    raw_response_ref=(
                        f"semantic-paper:fill:{execution_sequence}"
                    ),
                )
                fills = fills + (fill,)
                cash, positions = _apply_fill(
                    fill,
                    cash=cash,
                    positions=positions,
                )
            self._save_state(
                state.model_copy(
                    update={
                        "cash": cash,
                        "positions": positions,
                        "orders": state.orders + (order,),
                        "fills": fills,
                        "order_sequence": order_sequence,
                        "execution_sequence": execution_sequence,
                        "updated_at": datetime.now(UTC),
                    }
                )
            )
            return order

    def account_snapshot(self) -> LiveAccountSnapshot:
        state = self._load_state()
        self._require_identity(state)
        return LiveAccountSnapshot(
            broker_name=state.broker_name,
            account_id=state.account_id,
            broker_environment=state.broker_environment,
            cash=state.cash,
            buying_power=state.cash,
            positions=state.positions,
            open_order_ids=tuple(
                order.broker_order_id or order.client_order_id
                for order in self.open_orders()
            ),
            raw_response_ref=f"semantic-paper:state:{self._state_path}",
        )

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        return tuple(
            order
            for order in self._load_state().orders
            if order.status
            not in {
                LiveOrderStatus.CANCELLED,
                LiveOrderStatus.FILLED,
                LiveOrderStatus.REJECTED,
            }
        )

    def has_open_orders(self) -> bool:
        return bool(self.open_orders())

    def asset_trading_details(self, symbol: str) -> AssetTradingDetails:
        return AssetTradingDetails(
            symbol=symbol,
            tradable=True,
            shortable=True,
            easy_to_borrow=True,
        )

    def fills(self) -> tuple[LiveFillRecord, ...]:
        return self._load_state().fills

    def refresh_order_record(self, record: LiveOrderRecord) -> LiveOrderRecord:
        orders = self.orders_by_client_order_id(record.client_order_id)
        return orders[0] if len(orders) == 1 else record

    def orders_by_client_order_id(
        self,
        client_order_id: str,
    ) -> tuple[LiveOrderRecord, ...]:
        return tuple(
            order
            for order in self._load_state().orders
            if order.client_order_id == client_order_id
        )

    def _lock(self) -> FileLock:
        return FileLock(
            path=self._lock_path,
            lock_name=f"semantic-paper-state:{self._state_path.name}",
            stale_after_seconds=300,
        )

    def _load_state(self) -> SemanticPaperBrokerState:
        if not self._state_path.exists():
            return self._initial_state
        return SemanticPaperBrokerState.model_validate_json(
            self._state_path.read_text()
        )

    def _save_state(self, state: SemanticPaperBrokerState) -> None:
        self._state_path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._state_path.with_name(
            f".{self._state_path.name}.{uuid4()}.tmp"
        )
        try:
            with temporary.open("w") as file:
                file.write(state.model_dump_json(indent=2) + "\n")
                file.flush()
                os.fsync(file.fileno())
            os.replace(temporary, self._state_path)
            directory = os.open(self._state_path.parent, os.O_RDONLY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        finally:
            temporary.unlink(missing_ok=True)

    def _require_identity(self, state: SemanticPaperBrokerState) -> None:
        expected = self._initial_state
        if (
            state.broker_name != expected.broker_name
            or state.account_id != expected.account_id
            or state.broker_environment != expected.broker_environment
        ):
            raise ValueError("semantic paper state belongs to another account")


class SemanticPaperBrokerAdapter(LiveBrokerAdapter):
    """Live-shaped artifact adapter that permits local paper safety only."""

    def _require_live_allowed(self, safety_check: TradingSafetyCheck) -> None:
        _require_paper_safety(safety_check)


def _require_paper_safety(safety_check: TradingSafetyCheck) -> None:
    if safety_check.allowed and safety_check.mode == TradingMode.PAPER:
        return
    raise ValueError("semantic paper orders require an allowed paper check")


def _rejection_reason(
    request: OrderRequest,
    *,
    cash: float,
    reference_price: float,
) -> str | None:
    if (
        request.side == OrderSide.BUY
        and request.quantity * reference_price > cash
    ):
        return "insufficient paper cash"
    return None


def _apply_fill(
    fill: LiveFillRecord,
    *,
    cash: float,
    positions: tuple[Position, ...],
) -> tuple[float, tuple[Position, ...]]:
    by_symbol = {position.symbol: position for position in positions}
    existing = by_symbol.get(fill.symbol)
    old_quantity = existing.quantity if existing is not None else 0
    delta = fill.quantity if fill.side == OrderSide.BUY else -fill.quantity
    new_quantity = old_quantity + delta
    cash += -fill.notional if fill.side == OrderSide.BUY else fill.notional
    if new_quantity == 0:
        by_symbol.pop(fill.symbol, None)
    else:
        by_symbol[fill.symbol] = Position(
            symbol=fill.symbol,
            quantity=new_quantity,
            average_price=_updated_average_price(
                existing=existing,
                new_quantity=new_quantity,
                fill=fill,
            ),
            last_price=fill.price,
        )
    return cash, tuple(sorted(by_symbol.values(), key=lambda item: item.symbol))


def _updated_average_price(
    *,
    existing: Position | None,
    new_quantity: int,
    fill: LiveFillRecord,
) -> float:
    if existing is None or existing.quantity * new_quantity < 0:
        return fill.price
    if abs(new_quantity) <= abs(existing.quantity):
        return existing.average_price
    added_quantity = abs(new_quantity) - abs(existing.quantity)
    return (
        abs(existing.quantity) * existing.average_price
        + added_quantity * fill.price
    ) / abs(new_quantity)
