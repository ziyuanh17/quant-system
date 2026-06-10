from datetime import UTC, datetime
from enum import StrEnum
from uuid import uuid4

from pydantic import Field, model_validator

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


class LiveOrderStatus(StrEnum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    UNKNOWN = "unknown"


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


class AssetTradingDetails(FrozenModel):
    """Broker-neutral asset permissions used by pre-trade risk checks."""

    symbol: str
    tradable: bool
    shortable: bool
    easy_to_borrow: bool


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
    short_selling_policy: "ShortSellingPolicy" = Field(
        default_factory=lambda: ShortSellingPolicy()
    )


class ShortSellingPolicy(FrozenModel):
    """Fail-closed limits for intentionally opening short positions."""

    enabled: bool = False
    max_short_position_notional: float | None = Field(default=None, gt=0)
    max_total_short_exposure_pct_equity: float | None = Field(
        default=None,
        gt=0,
    )
    max_gross_exposure_pct_equity: float | None = Field(default=None, gt=0)
    min_buying_power_buffer_pct: float | None = Field(
        default=None,
        ge=0,
        lt=1,
    )

    @model_validator(mode="after")
    def require_limits_when_enabled(self) -> "ShortSellingPolicy":
        if not self.enabled:
            return self
        required_limits = {
            "max_short_position_notional": self.max_short_position_notional,
            "max_total_short_exposure_pct_equity": (
                self.max_total_short_exposure_pct_equity
            ),
            "max_gross_exposure_pct_equity": (
                self.max_gross_exposure_pct_equity
            ),
            "min_buying_power_buffer_pct": self.min_buying_power_buffer_pct,
        }
        missing = [
            name for name, value in required_limits.items() if value is None
        ]
        if missing:
            raise ValueError(
                "enabled short selling requires explicit limits: "
                + ", ".join(missing)
            )
        return self


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


class LiveOrderRecord(FrozenModel):
    """Broker order audit record for future live adapters.

    The model is intentionally broker-neutral. A live adapter should translate
    provider-specific responses into this shape before writing local artifacts.
    """

    id: str = Field(default_factory=lambda: str(uuid4()))
    client_order_id: str
    broker_order_id: str | None = None
    broker_name: str
    account_id: str
    broker_environment: str
    request: OrderRequest
    reference_price: float = Field(gt=0)
    notional: float = Field(gt=0)
    safety_check: TradingSafetyCheck
    status: LiveOrderStatus
    rejection_reason: str | None = None
    raw_response_ref: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    submitted_at: datetime | None = None
    broker_updated_at: datetime | None = None
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


class LiveFillRecord(FrozenModel):
    """Broker execution/fill audit record for future live adapters."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    order_record_id: str
    client_order_id: str
    broker_order_id: str
    broker_execution_id: str | None = None
    broker_name: str
    account_id: str
    broker_environment: str
    symbol: str
    side: OrderSide
    quantity: int = Field(gt=0)
    price: float = Field(gt=0)
    commission: float = Field(default=0, ge=0)
    raw_response_ref: str | None = None
    filled_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    recorded_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def notional(self) -> float:
        return self.quantity * self.price


class LiveAccountSnapshot(FrozenModel):
    """Sanitized broker account snapshot for future live reconciliation."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    broker_name: str
    account_id: str
    broker_environment: str
    cash: float = Field(ge=0)
    buying_power: float = Field(ge=0)
    positions: tuple[Position, ...] = ()
    open_order_ids: tuple[str, ...] = ()
    captured_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    raw_response_ref: str | None = None

    @property
    def equity(self) -> float:
        return self.cash + sum(
            position.market_value for position in self.positions
        )


class LiveReconciliationStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"


class LiveReconciliationDifference(FrozenModel):
    field: str
    local_value: str
    broker_value: str
    message: str


class LiveReconciliationReport(FrozenModel):
    """Read-only comparison between local live artifacts and broker truth."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    broker_name: str
    account_id: str
    broker_environment: str
    local_order_count: int = Field(ge=0)
    broker_order_count: int = Field(ge=0)
    local_fill_count: int = Field(ge=0)
    broker_fill_count: int = Field(ge=0)
    local_position_count: int = Field(ge=0)
    broker_position_count: int = Field(ge=0)
    status: LiveReconciliationStatus
    differences: tuple[LiveReconciliationDifference, ...] = ()
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    @property
    def passed(self) -> bool:
        return self.status == LiveReconciliationStatus.PASSED

    @property
    def difference_count(self) -> int:
        return len(self.differences)


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
