from collections.abc import Sequence
from datetime import datetime
from typing import Any, Protocol

from pydantic import Field

from quant.models.base import FrozenModel
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    Position,
    TradingSafetyCheck,
)


class AlpacaPaperConfig(FrozenModel):
    """Config values needed before constructing an Alpaca paper client."""

    api_key: str
    secret_key: str
    account_id: str
    url_override: str | None = None


class AlpacaTradingClientProtocol(Protocol):
    """Tiny subset of alpaca-py TradingClient used by the future adapter."""

    def submit_order(self, order_data: object) -> object:
        """Submit an order through Alpaca."""
        ...

    def get_orders(self, filter: object | None = None) -> list[object]:
        """Return Alpaca orders, optionally filtered."""
        ...

    def get_account(self) -> object:
        """Return Alpaca account details."""
        ...

    def get_all_positions(self) -> list[object]:
        """Return Alpaca open positions."""
        ...


class AlpacaMarketOrderRequest(FrozenModel):
    """SDK-free stand-in for the future Alpaca MarketOrderRequest."""

    symbol: str
    side: str
    qty: int = Field(gt=0)
    time_in_force: str = "day"
    client_order_id: str


def map_order_request_to_alpaca_market_order(
    request: OrderRequest,
    *,
    client_order_id: str,
) -> AlpacaMarketOrderRequest:
    """Map an internal order request into an SDK-free Alpaca request shape."""
    return AlpacaMarketOrderRequest(
        symbol=request.symbol,
        side=request.side.value,
        qty=request.quantity,
        client_order_id=client_order_id,
    )


def map_alpaca_order_status(status: object) -> LiveOrderStatus:
    """Map Alpaca order status values into internal live order status."""
    normalized = _string_value(status).lower()
    if normalized == "filled":
        return LiveOrderStatus.FILLED
    if normalized == "partially_filled":
        return LiveOrderStatus.PARTIALLY_FILLED
    if normalized in {"canceled", "cancelled", "expired"}:
        return LiveOrderStatus.CANCELLED
    if normalized == "rejected":
        return LiveOrderStatus.REJECTED
    if normalized in {
        "new",
        "accepted",
        "pending_new",
        "accepted_for_bidding",
        "pending_cancel",
        "pending_replace",
    }:
        return LiveOrderStatus.ACCEPTED
    return LiveOrderStatus.UNKNOWN


def map_alpaca_order_record(
    order: object,
    *,
    request: OrderRequest,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    account_id: str,
    broker_environment: str = "paper",
) -> LiveOrderRecord:
    """Map an Alpaca-shaped order object into a broker-neutral order record."""
    broker_order_id = _optional_attr(order, "id")
    client_order_id = _optional_attr(order, "client_order_id")
    if client_order_id is None:
        raise ValueError("Alpaca order is missing client_order_id")
    rejection_reason = _optional_attr(order, "failed_at")
    status = map_alpaca_order_status(_optional_attr(order, "status"))
    return LiveOrderRecord(
        client_order_id=client_order_id,
        broker_order_id=broker_order_id,
        broker_name="alpaca-paper",
        account_id=account_id,
        broker_environment=broker_environment,
        request=request,
        reference_price=reference_price,
        notional=request.quantity * reference_price,
        safety_check=safety_check,
        status=status,
        rejection_reason=(
            "alpaca order rejected"
            if status == LiveOrderStatus.REJECTED and rejection_reason is None
            else rejection_reason
        ),
        raw_response_ref=(
            f"alpaca-paper:order:{broker_order_id}"
            if broker_order_id is not None
            else None
        ),
        submitted_at=_optional_datetime(order, "submitted_at"),
        broker_updated_at=_optional_datetime(order, "updated_at"),
    )


def map_alpaca_fill_records(
    order: object,
    *,
    order_record: LiveOrderRecord,
) -> tuple[LiveFillRecord, ...]:
    """Create fill records from an Alpaca-shaped filled order when possible."""
    status = map_alpaca_order_status(_optional_attr(order, "status"))
    if status not in {
        LiveOrderStatus.FILLED,
        LiveOrderStatus.PARTIALLY_FILLED,
    }:
        return ()

    filled_quantity = _optional_int(order, "filled_qty")
    filled_price = _optional_float(order, "filled_avg_price")
    if filled_quantity is None or filled_price is None:
        return ()

    execution_id = _optional_attr(order, "execution_id") or (
        f"{order_record.broker_order_id}:{filled_quantity}:{filled_price}"
    )
    # Alpaca order objects may omit `filled_at` for partial fills. The local
    # audit model still needs a concrete timestamp, so fall back to broker
    # update time and then local record creation time.
    filled_at = (
        _optional_datetime(order, "filled_at")
        or order_record.broker_updated_at
        or order_record.recorded_at
    )
    return (
        LiveFillRecord(
            order_record_id=order_record.id,
            client_order_id=order_record.client_order_id,
            broker_order_id=(
                order_record.broker_order_id or order_record.client_order_id
            ),
            broker_execution_id=execution_id,
            broker_name=order_record.broker_name,
            account_id=order_record.account_id,
            broker_environment=order_record.broker_environment,
            symbol=order_record.request.symbol,
            side=order_record.request.side,
            quantity=filled_quantity,
            price=filled_price,
            raw_response_ref=f"alpaca-paper:fill:{execution_id}",
            filled_at=filled_at,
        ),
    )


def map_alpaca_account_snapshot(
    account: object,
    positions: Sequence[object],
    *,
    broker_environment: str = "paper",
) -> LiveAccountSnapshot:
    """Map Alpaca-shaped account and position objects into a snapshot."""
    account_id = _required_attr(account, "id")
    return LiveAccountSnapshot(
        broker_name="alpaca-paper",
        account_id=account_id,
        broker_environment=broker_environment,
        cash=_required_float(account, "cash"),
        buying_power=_required_float(account, "buying_power"),
        positions=tuple(
            map_alpaca_position(position) for position in positions
        ),
        raw_response_ref=f"alpaca-paper:account:{account_id}",
    )


def map_alpaca_position(position: object) -> Position:
    """Map an Alpaca-shaped position object into an internal position."""
    return Position(
        symbol=_required_attr(position, "symbol"),
        quantity=_required_int(position, "qty"),
        average_price=_required_float(position, "avg_entry_price"),
        last_price=_position_last_price(position),
    )


def _position_last_price(position: object) -> float:
    current_price = _optional_float(position, "current_price")
    if current_price is not None:
        return current_price
    return _required_float(position, "market_value") / _required_int(
        position, "qty"
    )


def _required_attr(source: object, name: str) -> str:
    value = _optional_attr(source, name)
    if value is None or value == "":
        raise ValueError(f"Alpaca object is missing {name}")
    return value


def _optional_attr(source: object, name: str) -> str | None:
    value = _get_value(source, name)
    if value is None:
        return None
    return _string_value(value)


def _required_float(source: object, name: str) -> float:
    value = _optional_float(source, name)
    if value is None:
        raise ValueError(f"Alpaca object is missing {name}")
    return value


def _optional_float(source: object, name: str) -> float | None:
    value = _get_value(source, name)
    if value is None or value == "":
        return None
    return float(value)


def _required_int(source: object, name: str) -> int:
    value = _optional_int(source, name)
    if value is None:
        raise ValueError(f"Alpaca object is missing {name}")
    return value


def _optional_int(source: object, name: str) -> int | None:
    value = _get_value(source, name)
    if value is None or value == "":
        return None
    return int(float(value))


def _optional_datetime(source: object, name: str) -> datetime | None:
    value = _get_value(source, name)
    if value is None or value == "":
        return None
    if isinstance(value, datetime):
        return value
    return datetime.fromisoformat(str(value))


def _get_value(source: object, name: str) -> Any:
    if isinstance(source, dict):
        return source.get(name)
    return getattr(source, name, None)


def _string_value(value: object) -> str:
    enum_value = getattr(value, "value", value)
    return str(enum_value)
