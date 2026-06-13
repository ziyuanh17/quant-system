from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from quant.models.base import FrozenModel
from quant.models.execution import LiveOrderStatus, OrderRequest, OrderSide

EXECUTION_LIFECYCLE_SCHEMA_VERSION = 2


class ExecutionPlanStatus(StrEnum):
    PLANNED = "planned"
    SUBMISSION_PENDING = "submission_pending"
    SUBMITTED = "submitted"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    AMBIGUOUS = "ambiguous"
    BLOCKED = "blocked"
    SATISFIED = "satisfied"


class BrokerLookupOutcome(StrEnum):
    FOUND = "found"
    NOT_FOUND = "not_found"
    UNAVAILABLE = "unavailable"
    CONFLICTING = "conflicting"


class ExecutionDriftStatus(StrEnum):
    CLEAR = "clear"
    DETECTED = "detected"
    INDETERMINATE = "indeterminate"


class ExecutionLifecyclePolicy(FrozenModel):
    execution_policy_version: str = Field(min_length=1)
    reconciliation_policy_version: str = Field(min_length=1)
    drift_policy_version: str = Field(min_length=1)


class ExecutionPlan(FrozenModel):
    """Immutable claim over one approved risk-target revision."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    execution_plan_id: str = Field(min_length=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    portfolio_target_id: str = Field(min_length=1)
    contributor_set_id: str = Field(min_length=1)
    contributor_set_revision: int = Field(ge=1)
    source_strategy_decision_ids: tuple[str, ...] = Field(min_length=1)
    account_snapshot_id: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    broker_environment: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    current_quantity: int
    target_quantity: int
    order_request: OrderRequest | None = None
    client_order_id: str = Field(min_length=1)
    execution_policy_version: str = Field(min_length=1)
    reconciliation_policy_version: str = Field(min_length=1)
    drift_policy_version: str = Field(min_length=1)
    initial_status: Literal[ExecutionPlanStatus.PLANNED] = (
        ExecutionPlanStatus.PLANNED
    )
    created_at: datetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_order_delta(self) -> "ExecutionPlan":
        delta = self.target_quantity - self.current_quantity
        if delta == 0 and self.order_request is not None:
            raise ValueError("satisfied target must not create an order")
        if delta != 0 and self.order_request is None:
            raise ValueError("unsatisfied target requires an order")
        if self.order_request is None:
            return self
        expected_side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        if (
            self.order_request.symbol != self.symbol
            or self.order_request.side != expected_side
            or self.order_request.quantity != abs(delta)
        ):
            raise ValueError("order request must exactly match target delta")
        return self


class ExecutionEvent(FrozenModel):
    """One immutable lifecycle transition."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    event_id: str = Field(min_length=1)
    execution_plan_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    previous_status: ExecutionPlanStatus
    new_status: ExecutionPlanStatus
    occurred_at: datetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
    broker_order_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def submitted_event_requires_broker_order(self) -> "ExecutionEvent":
        if (
            self.new_status == ExecutionPlanStatus.SUBMITTED
            and len(self.broker_order_ids) != 1
        ):
            raise ValueError(
                "submitted execution events require one broker order ID"
            )
        return self


class BrokerOrderLookupEvidence(FrozenModel):
    """Durable evidence from deterministic client-order-ID recovery."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    evidence_id: str = Field(min_length=1)
    execution_plan_id: str = Field(min_length=1)
    client_order_id: str = Field(min_length=1)
    outcome: BrokerLookupOutcome
    order_record_ids: tuple[str, ...] = ()
    broker_order_ids: tuple[str, ...] = ()
    order_statuses: tuple[LiveOrderStatus, ...] = ()
    order_identity_results: tuple[str, ...] = ()
    occurred_at: datetime
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_lookup_outcome(self) -> "BrokerOrderLookupEvidence":
        counts = {
            len(self.order_record_ids),
            len(self.broker_order_ids),
            len(self.order_statuses),
            len(self.order_identity_results),
        }
        if len(counts) != 1:
            raise ValueError("lookup order evidence fields must align")
        count = len(self.order_record_ids)
        if self.outcome == BrokerLookupOutcome.FOUND and count != 1:
            raise ValueError("found lookup requires exactly one order")
        if self.outcome == BrokerLookupOutcome.CONFLICTING and count < 1:
            raise ValueError("conflicting lookup requires order evidence")
        if (
            self.outcome
            in {
                BrokerLookupOutcome.NOT_FOUND,
                BrokerLookupOutcome.UNAVAILABLE,
            }
            and count
        ):
            raise ValueError("empty lookup outcomes must not include orders")
        return self


class ExecutionDriftObservation(FrozenModel):
    """Detect-only comparison after an execution has been satisfied."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    observation_id: str = Field(min_length=1)
    execution_plan_id: str = Field(min_length=1)
    drift_policy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    broker_environment: str = Field(min_length=1)
    approved_target_quantity: int
    broker_position_quantity: int
    open_order_ids: tuple[str, ...] = ()
    status: ExecutionDriftStatus
    observed_at: datetime
    reason: str = Field(min_length=1)
