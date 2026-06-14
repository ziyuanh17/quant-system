"""Adapt strategy decisions to the local paper broker."""

from typing import Protocol

from quant.execution.paper_broker import PaperBroker
from quant.models.execution import (
    BrokerAccountSnapshot,
    BrokerMode,
    DryRunOrderRecord,
    OrderRequest,
    PaperBrokerState,
    PaperTradeRecord,
    PortfolioSnapshot,
    TradingMode,
    TradingSafetyCheck,
)


class BrokerAdapter(Protocol):
    """Execution boundary shared by paper and future live broker adapters."""

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        market_price: float,
    ) -> PaperTradeRecord:
        """Submit a market order and return the resulting order audit data."""
        ...

    def snapshot(self) -> PortfolioSnapshot:
        """Return the latest account snapshot without placing an order."""
        ...

    def account_snapshot(self) -> BrokerAccountSnapshot:
        """Return broker-mode metadata plus the latest portfolio snapshot."""
        ...


class SignalExecutionBroker(BrokerAdapter, Protocol):
    """Broker behavior needed by strategy-to-broker signal execution."""

    def has_processed_signal(self, key: str) -> bool:
        """Report whether a signal idempotency key has already executed."""
        ...

    def mark_signal_processed(self, key: str) -> None:
        """Record that a signal idempotency key has been handled."""
        ...


class PaperBrokerAdapter:
    """Adapter that exposes the paper broker through the broker boundary."""

    mode = BrokerMode.PAPER

    def __init__(self, broker: PaperBroker) -> None:
        self._broker = broker

    @classmethod
    def from_state(cls, state: PaperBrokerState) -> "PaperBrokerAdapter":
        return cls(PaperBroker.from_state(state))

    @classmethod
    def from_initial_cash(
        cls,
        *,
        initial_cash: float,
    ) -> "PaperBrokerAdapter":
        return cls(PaperBroker(initial_cash=initial_cash))

    def state(self) -> PaperBrokerState:
        return self._broker.state()

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        market_price: float,
    ) -> PaperTradeRecord:
        return self._broker.submit_market_order(
            request,
            market_price=market_price,
        )

    def snapshot(self) -> PortfolioSnapshot:
        return self._broker.snapshot()

    def account_snapshot(self) -> BrokerAccountSnapshot:
        return BrokerAccountSnapshot(
            mode=self.mode,
            portfolio=self.snapshot(),
        )

    def has_processed_signal(self, key: str) -> bool:
        return self._broker.has_processed_signal(key)

    def mark_signal_processed(self, key: str) -> None:
        self._broker.mark_signal_processed(key)


class DryRunBrokerAdapter:
    """Live-shaped adapter that records intended orders without submission."""

    mode = BrokerMode.DRY_RUN

    def __init__(self, *, broker_name: str) -> None:
        if not broker_name:
            raise ValueError("broker_name is required for dry-run orders")
        self._broker_name = broker_name

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        market_price: float,
        safety_check: TradingSafetyCheck,
    ) -> DryRunOrderRecord:
        if not safety_check.allowed or safety_check.mode != TradingMode.DRY_RUN:
            raise ValueError("dry-run orders require an allowed dry-run check")

        return DryRunOrderRecord(
            request=request,
            market_price=market_price,
            notional=request.quantity * market_price,
            broker_name=self._broker_name,
            safety_check=safety_check,
        )
