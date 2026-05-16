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
    DRY_RUN = "dry_run"
    LIVE = "live"


class TradingMode(StrEnum):
    PAPER = "paper"
    DRY_RUN = "dry_run"
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


class TradingSafetyConfig(FrozenModel):
    """Explicit controls required before any future live trading path runs."""

    mode: TradingMode = TradingMode.PAPER
    live_trading_enabled: bool = False
    live_trading_confirmation: str | None = None
    max_order_notional: float | None = Field(default=None, gt=0)
    broker_name: str | None = None


class TradingSafetyCheck(FrozenModel):
    mode: TradingMode
    allowed: bool
    issues: tuple[str, ...] = ()

    @property
    def reason(self) -> str:
        if self.allowed:
            return "trading mode is allowed"
        return "; ".join(self.issues)


class DryRunOrderStatus(StrEnum):
    WOULD_SUBMIT = "would_submit"


class DryRunOrderRecord(FrozenModel):
    """Intended broker order that was recorded without being submitted."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    request: OrderRequest
    market_price: float = Field(gt=0)
    notional: float = Field(gt=0)
    status: DryRunOrderStatus = DryRunOrderStatus.WOULD_SUBMIT
    trading_mode: TradingMode = TradingMode.DRY_RUN
    broker_name: str
    safety_check: TradingSafetyCheck
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class PaperDryRunComparisonStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class PaperDryRunDifference(FrozenModel):
    field: str
    paper_value: str
    dry_run_value: str
    message: str


class PaperDryRunComparisonReport(FrozenModel):
    """Read-only comparison between paper signal and dry-run order artifacts."""

    paper_signal_path: str
    dry_run_order_path: str | None
    status: PaperDryRunComparisonStatus
    paper_action: PaperSignalAction
    dry_run_side: OrderSide | None = None
    paper_symbol: str
    dry_run_symbol: str | None = None
    paper_quantity: int | None = None
    dry_run_quantity: int | None = None
    paper_market_price: float
    dry_run_market_price: float | None = None
    paper_signal_date: str
    difference_tolerance: float
    difference_count: int
    differences: tuple[PaperDryRunDifference, ...] = ()

    @property
    def passed(self) -> bool:
        return self.status == PaperDryRunComparisonStatus.PASSED


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
