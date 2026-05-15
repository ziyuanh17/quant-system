from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field

from quant.models.base import FrozenModel


class OrderSide(StrEnum):
    BUY = "buy"
    SELL = "sell"


class OrderType(StrEnum):
    MARKET = "market"


class OrderStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FILLED = "filled"


class RiskDecision(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class PaperSignalAction(StrEnum):
    BUY = "buy"
    SELL = "sell"
    HOLD = "hold"


class BrokerMode(StrEnum):
    PAPER = "paper"
    LIVE = "live"


class OrderRequest(FrozenModel):
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    order_type: OrderType = OrderType.MARKET


class RiskCheckResult(FrozenModel):
    decision: RiskDecision
    reason: str | None = None

    @property
    def approved(self) -> bool:
        return self.decision == RiskDecision.APPROVED


class Order(FrozenModel):
    id: str = Field(default_factory=lambda: str(uuid4()))
    request: OrderRequest
    status: OrderStatus
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    risk: RiskCheckResult


class Fill(FrozenModel):
    order_id: str
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    filled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def notional(self) -> float:
        return self.quantity * self.price


class Position(FrozenModel):
    symbol: str
    quantity: int
    average_price: float = Field(ge=0)
    last_price: float = Field(gt=0)

    @property
    def market_value(self) -> float:
        return self.quantity * self.last_price


class PortfolioSnapshot(FrozenModel):
    cash: float = Field(ge=0)
    positions: tuple[Position, ...]
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def equity(self) -> float:
        return self.cash + sum(
            position.market_value for position in self.positions
        )


class BrokerAccountSnapshot(FrozenModel):
    """Broker-facing account view used before any real broker integration."""

    mode: BrokerMode
    portfolio: PortfolioSnapshot


class PaperBrokerState(FrozenModel):
    """Persisted paper account state between scheduled runs."""

    cash: float = Field(ge=0)
    positions: tuple[Position, ...] = ()
    processed_signal_keys: tuple[str, ...] = ()
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaperTradeRecord(FrozenModel):
    order: Order
    fill: Fill | None
    snapshot: PortfolioSnapshot


class PaperSignalDecision(FrozenModel):
    symbol: str
    action: PaperSignalAction
    signal_date: str
    market_price: float = Field(gt=0)
    reason: str
    idempotency_key: str


class PaperSignalRecord(FrozenModel):
    decision: PaperSignalDecision
    trade: PaperTradeRecord | None
    snapshot: PortfolioSnapshot
    skipped: bool = False


class PaperStateDifference(FrozenModel):
    field: str
    expected: str
    actual: str
    message: str


class PaperStateReconciliationReport(FrozenModel):
    """Read-only comparison between paper state and signal audit records."""

    state_path: str
    signal_records_dir: str
    signal_record_count: int
    filled_trade_count: int
    expected_cash: float
    actual_cash: float
    expected_positions: tuple[Position, ...]
    actual_positions: tuple[Position, ...]
    expected_processed_signal_keys: tuple[str, ...]
    actual_processed_signal_keys: tuple[str, ...]
    differences: tuple[PaperStateDifference, ...] = ()

    @property
    def passed(self) -> bool:
        return len(self.differences) == 0

    @property
    def difference_count(self) -> int:
        return len(self.differences)
