from collections.abc import Sequence
from datetime import datetime
from typing import TYPE_CHECKING, Any, Protocol

from pydantic import Field

from quant.models.base import FrozenModel
from quant.models.execution import (
    AssetTradingDetails,
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    Position,
    TradingSafetyCheck,
)

if TYPE_CHECKING:
    from quant.execution.alpaca_sdk import AlpacaTradingSdk


class AlpacaPaperConfig(FrozenModel):
    """Config values needed before constructing an Alpaca paper client."""

    api_key: str = Field(min_length=1)
    secret_key: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    url_override: str | None = None


class AlpacaTradingClientProtocol(Protocol):
    """Tiny subset of alpaca-py TradingClient used by the future adapter."""

    def submit_order(self, order_data: object) -> object:
        """Submit an order through Alpaca."""
        ...

    def get_orders(self, filter: object | None = None) -> list[object]:
        """Return Alpaca orders, optionally filtered."""
        ...

    def get_order_by_id(self, order_id: str) -> object:
        """Return one Alpaca order by broker order ID."""
        ...

    def get_order_by_client_id(self, client_id: str) -> object:
        """Return one Alpaca order by deterministic client order ID."""
        ...

    def get_account(self) -> object:
        """Return Alpaca account details."""
        ...

    def get_all_positions(self) -> list[object]:
        """Return Alpaca open positions."""
        ...

    def get_asset(self, symbol_or_asset_id: str) -> object:
        """Return current Alpaca metadata for one asset."""
        ...


class AlpacaMarketOrderRequest(FrozenModel):
    """SDK-free stand-in for the future Alpaca MarketOrderRequest."""

    symbol: str
    side: str
    qty: int = Field(gt=0)
    time_in_force: str = "day"
    client_order_id: str


class AlpacaPaperBrokerClient:
    """Alpaca paper implementation of the live broker client boundary."""

    def __init__(
        self,
        *,
        config: AlpacaPaperConfig,
        trading_client: AlpacaTradingClientProtocol | None = None,
        sdk: "AlpacaTradingSdk | None" = None,
    ) -> None:
        self._config = config
        self._sdk = sdk
        self._trading_client = trading_client or self._build_trading_client()
        self._orders_by_client_id: dict[str, LiveOrderRecord] = {}
        # Alpaca order polling does not include the original strategy request,
        # so keep the local context needed to map known broker orders later.
        self._order_contexts: dict[str, _AlpacaOrderContext] = {}
        self._fills_by_execution_id: dict[str, LiveFillRecord] = {}

    @property
    def trading_client_for_testing(self) -> AlpacaTradingClientProtocol:
        """Expose the wrapped client for no-network constructor tests."""
        return self._trading_client

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
        alpaca_request = map_order_request_to_alpaca_market_order(
            request,
            client_order_id=client_order_id,
        )
        order_data = self._build_sdk_market_order(alpaca_request)
        raw_order = self._trading_client.submit_order(order_data)
        record = map_alpaca_order_record(
            raw_order,
            request=request,
            reference_price=reference_price,
            safety_check=safety_check,
            account_id=self._config.account_id,
        )
        self._orders_by_client_id[record.client_order_id] = record
        self._order_contexts[record.client_order_id] = _AlpacaOrderContext(
            request=request,
            reference_price=reference_price,
            safety_check=safety_check,
        )
        self._remember_fills(raw_order, order_record=record)
        return record

    def account_snapshot(self) -> LiveAccountSnapshot:
        return map_alpaca_account_snapshot(
            self._trading_client.get_account(),
            self._trading_client.get_all_positions(),
        )

    def asset_trading_details(self, symbol: str) -> AssetTradingDetails:
        """Map Alpaca's current tradability and borrow-availability flags."""
        raw_asset = self._trading_client.get_asset(symbol)
        return AssetTradingDetails(
            symbol=str(_required_attr(raw_asset, "symbol")),
            tradable=_required_bool(raw_asset, "tradable"),
            shortable=_required_bool(raw_asset, "shortable"),
            easy_to_borrow=_required_bool(raw_asset, "easy_to_borrow"),
        )

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        terminal = {
            LiveOrderStatus.CANCELLED,
            LiveOrderStatus.FILLED,
            LiveOrderStatus.REJECTED,
        }
        records: list[LiveOrderRecord] = []
        for raw_order in self._trading_client.get_orders():
            client_order_id = _optional_attr(raw_order, "client_order_id")
            if client_order_id is None:
                continue
            context = self._order_contexts.get(client_order_id)
            if context is None:
                continue
            record = map_alpaca_order_record(
                raw_order,
                request=context.request,
                reference_price=context.reference_price,
                safety_check=context.safety_check,
                account_id=self._config.account_id,
            )
            self._orders_by_client_id[client_order_id] = record
            self._remember_fills(raw_order, order_record=record)
            if record.status not in terminal:
                records.append(record)
        return tuple(records)

    def has_open_orders(self) -> bool:
        """Detect unsettled broker orders, including orders from older runs."""
        terminal = {
            LiveOrderStatus.CANCELLED,
            LiveOrderStatus.FILLED,
            LiveOrderStatus.REJECTED,
        }
        return any(
            map_alpaca_order_status(_required_attr(raw_order, "status"))
            not in terminal
            for raw_order in self._trading_client.get_orders()
        )

    def fills(self) -> tuple[LiveFillRecord, ...]:
        # Reconciliation remembers durable local order records before asking
        # for fills. Refresh those exact broker orders by ID so old fills do
        # not disappear when Alpaca's default order-list window changes.
        for order_record in tuple(self._orders_by_client_id.values()):
            if order_record.broker_order_id is None:
                continue
            self.refresh_order_record(order_record)
        return tuple(self._fills_by_execution_id.values())

    def remember_order_record(self, record: LiveOrderRecord) -> None:
        """Keep local request context for later broker polling."""
        self._orders_by_client_id[record.client_order_id] = record
        self._order_contexts[record.client_order_id] = _AlpacaOrderContext(
            request=record.request,
            reference_price=record.reference_price,
            safety_check=record.safety_check,
        )

    def refresh_order_record(
        self,
        record: LiveOrderRecord,
    ) -> LiveOrderRecord:
        """Refresh a known local order from current Alpaca broker truth."""
        if record.broker_order_id is None:
            raise ValueError("cannot refresh order without broker_order_id")
        self.remember_order_record(record)
        raw_order = self._trading_client.get_order_by_id(record.broker_order_id)
        context = self._order_contexts[record.client_order_id]
        refreshed = map_alpaca_order_record(
            raw_order,
            request=context.request,
            reference_price=context.reference_price,
            safety_check=context.safety_check,
            account_id=self._config.account_id,
        )
        refreshed = refreshed.model_copy(update={"id": record.id})
        self._orders_by_client_id[refreshed.client_order_id] = refreshed
        self._remember_fills(raw_order, order_record=refreshed)
        return refreshed

    def orders_by_client_order_id(
        self,
        client_order_id: str,
    ) -> tuple[LiveOrderRecord, ...]:
        """Recover one known execution by deterministic client order ID."""
        context = self._order_contexts.get(client_order_id)
        if context is None:
            raise RuntimeError(
                "Alpaca client-order lookup requires durable order context"
            )
        raw_order = self._trading_client.get_order_by_client_id(client_order_id)
        record = map_alpaca_order_record(
            raw_order,
            request=context.request,
            reference_price=context.reference_price,
            safety_check=context.safety_check,
            account_id=self._config.account_id,
        )
        existing = self._orders_by_client_id.get(client_order_id)
        if existing is not None:
            record = record.model_copy(update={"id": existing.id})
        self._orders_by_client_id[client_order_id] = record
        self._remember_fills(raw_order, order_record=record)
        return (record,)

    def _build_trading_client(self) -> AlpacaTradingClientProtocol:
        sdk = self._load_sdk()
        kwargs: dict[str, object] = {
            "api_key": self._config.api_key,
            "secret_key": self._config.secret_key,
            "paper": True,
        }
        if self._config.url_override is not None:
            kwargs["url_override"] = self._config.url_override
        return sdk.TradingClient(**kwargs)

    def _build_sdk_market_order(
        self,
        request: AlpacaMarketOrderRequest,
    ) -> object:
        # Keep alpaca-py imports lazy so default CI and normal imports do not
        # need the optional broker dependency installed.
        from quant.execution.alpaca_sdk import (
            build_alpaca_sdk_market_order_request,
        )

        return build_alpaca_sdk_market_order_request(
            request,
            sdk=self._sdk,
        )

    def _load_sdk(self) -> "AlpacaTradingSdk":
        if self._sdk is not None:
            return self._sdk
        from quant.execution.alpaca_sdk import load_alpaca_trading_sdk

        return load_alpaca_trading_sdk()

    def _remember_fills(
        self,
        raw_order: object,
        *,
        order_record: LiveOrderRecord,
    ) -> None:
        for fill in map_alpaca_fill_records(
            raw_order,
            order_record=order_record,
        ):
            fill_key = fill.broker_execution_id or fill.id
            self._fills_by_execution_id[fill_key] = fill


class _AlpacaOrderContext(FrozenModel):
    request: OrderRequest
    reference_price: float
    safety_check: TradingSafetyCheck


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


def _required_bool(source: object, name: str) -> bool:
    value = _get_value(source, name)
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized == "true":
            return True
        if normalized == "false":
            return False
    raise ValueError(f"Alpaca object has invalid boolean {name}")


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
