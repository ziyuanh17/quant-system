from typing import Protocol

from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    Position,
    TradingMode,
    TradingSafetyCheck,
)


class LiveBrokerClient(Protocol):
    """Minimal broker-client boundary for future live adapter tests."""

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        """Submit a market order and return a broker-neutral audit record."""
        ...

    def account_snapshot(self) -> LiveAccountSnapshot:
        """Return a sanitized account snapshot without placing an order."""
        ...

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        """Return broker orders that are not terminal."""
        ...

    def fills(self) -> tuple[LiveFillRecord, ...]:
        """Return broker fills known to the client."""
        ...


class FakeLiveBrokerClient:
    """No-network live broker test double.

    The fake behaves like a tiny immediate-fill broker. It lets future live
    adapter tests exercise accepted, rejected, filled, and idempotent paths
    without credentials, SDKs, or network calls.
    """

    def __init__(
        self,
        *,
        initial_cash: float,
        broker_name: str = "fake-live",
        account_id: str = "fake-account",
        broker_environment: str = "paper",
        positions: tuple[Position, ...] = (),
    ) -> None:
        if initial_cash < 0:
            raise ValueError("initial_cash must be non-negative")
        self._cash = initial_cash
        self._broker_name = broker_name
        self._account_id = account_id
        self._broker_environment = broker_environment
        self._positions = {position.symbol: position for position in positions}
        self._orders: dict[str, LiveOrderRecord] = {}
        self._fills: list[LiveFillRecord] = []
        self._broker_order_seq = 0
        self._execution_seq = 0

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        if reference_price <= 0:
            raise ValueError("reference_price must be positive")
        if not safety_check.allowed or safety_check.mode != TradingMode.LIVE:
            raise ValueError("fake live orders require an allowed live check")
        if client_order_id in self._orders:
            return self._orders[client_order_id]

        notional = request.quantity * reference_price
        rejection_reason = self._risk_rejection_reason(request, notional)
        if rejection_reason is not None:
            record = self._build_order_record(
                request=request,
                reference_price=reference_price,
                client_order_id=client_order_id,
                safety_check=safety_check,
                status=LiveOrderStatus.REJECTED,
                rejection_reason=rejection_reason,
            )
            self._orders[client_order_id] = record
            return record

        record = self._build_order_record(
            request=request,
            reference_price=reference_price,
            client_order_id=client_order_id,
            safety_check=safety_check,
            status=LiveOrderStatus.FILLED,
        )
        self._orders[client_order_id] = record
        fill = self._build_fill_record(
            record=record,
            price=reference_price,
        )
        self._fills.append(fill)
        self._apply_fill(fill)
        return record

    def account_snapshot(self) -> LiveAccountSnapshot:
        return LiveAccountSnapshot(
            broker_name=self._broker_name,
            account_id=self._account_id,
            broker_environment=self._broker_environment,
            cash=self._cash,
            buying_power=self._cash,
            positions=tuple(self._positions.values()),
            open_order_ids=tuple(
                order.broker_order_id or order.client_order_id
                for order in self.open_orders()
            ),
            raw_response_ref="fake-live:account-snapshot",
        )

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        terminal = {
            LiveOrderStatus.CANCELLED,
            LiveOrderStatus.FILLED,
            LiveOrderStatus.REJECTED,
        }
        return tuple(
            order
            for order in self._orders.values()
            if order.status not in terminal
        )

    def fills(self) -> tuple[LiveFillRecord, ...]:
        return tuple(self._fills)

    def _risk_rejection_reason(
        self,
        request: OrderRequest,
        notional: float,
    ) -> str | None:
        if request.side == OrderSide.BUY and notional > self._cash:
            return "insufficient buying power"
        position = self._positions.get(request.symbol)
        if (
            request.side == OrderSide.SELL
            and (position is None or position.quantity < request.quantity)
        ):
            return "insufficient position"
        return None

    def _build_order_record(
        self,
        *,
        request: OrderRequest,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
        status: LiveOrderStatus,
        rejection_reason: str | None = None,
    ) -> LiveOrderRecord:
        self._broker_order_seq += 1
        broker_order_id = f"fake-order-{self._broker_order_seq}"
        return LiveOrderRecord(
            client_order_id=client_order_id,
            broker_order_id=broker_order_id,
            broker_name=self._broker_name,
            account_id=self._account_id,
            broker_environment=self._broker_environment,
            request=request,
            reference_price=reference_price,
            notional=request.quantity * reference_price,
            safety_check=safety_check,
            status=status,
            rejection_reason=rejection_reason,
            raw_response_ref=f"fake-live:order:{broker_order_id}",
        )

    def _build_fill_record(
        self,
        *,
        record: LiveOrderRecord,
        price: float,
    ) -> LiveFillRecord:
        self._execution_seq += 1
        execution_id = f"fake-exec-{self._execution_seq}"
        return LiveFillRecord(
            order_record_id=record.id,
            client_order_id=record.client_order_id,
            broker_order_id=record.broker_order_id or record.client_order_id,
            broker_execution_id=execution_id,
            broker_name=self._broker_name,
            account_id=self._account_id,
            broker_environment=self._broker_environment,
            symbol=record.request.symbol,
            side=record.request.side,
            quantity=record.request.quantity,
            price=price,
            raw_response_ref=f"fake-live:fill:{execution_id}",
        )

    def _apply_fill(self, fill: LiveFillRecord) -> None:
        if fill.side == OrderSide.BUY:
            self._cash -= fill.notional + fill.commission
            self._positions[fill.symbol] = self._buy_position(fill)
            return

        self._cash += fill.notional - fill.commission
        existing = self._positions[fill.symbol]
        remaining_quantity = existing.quantity - fill.quantity
        if remaining_quantity == 0:
            del self._positions[fill.symbol]
            return
        self._positions[fill.symbol] = Position(
            symbol=fill.symbol,
            quantity=remaining_quantity,
            average_price=existing.average_price,
            last_price=fill.price,
        )

    def _buy_position(self, fill: LiveFillRecord) -> Position:
        existing = self._positions.get(fill.symbol)
        if existing is None:
            return Position(
                symbol=fill.symbol,
                quantity=fill.quantity,
                average_price=fill.price,
                last_price=fill.price,
            )
        total_quantity = existing.quantity + fill.quantity
        total_cost = (
            existing.quantity * existing.average_price
            + fill.quantity * fill.price
        )
        return Position(
            symbol=fill.symbol,
            quantity=total_quantity,
            average_price=total_cost / total_quantity,
            last_price=fill.price,
        )
