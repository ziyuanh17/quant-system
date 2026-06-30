"""Define domain models for restart-safe target execution lifecycle."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import Field, model_validator

from quant.models.base import FrozenModel
from quant.models.execution import (
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)

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


class ExecutionDryRunStatus(StrEnum):
    WOULD_SUBMIT = "would_submit"
    ALREADY_SATISFIED = "already_satisfied"
    BLOCKED = "blocked"


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


class ExecutionTransitionLeg(FrozenModel):
    """One semantic leg in a target quantity transition."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    leg_id: str = Field(min_length=1)
    leg_index: int = Field(ge=1)
    semantic: str = Field(min_length=1)
    order_request: OrderRequest
    required_start_quantity: int
    required_end_quantity: int
    client_order_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_leg_delta(self) -> "ExecutionTransitionLeg":
        delta = self.required_end_quantity - self.required_start_quantity
        if delta == 0:
            raise ValueError("transition leg must change quantity")
        expected_side = OrderSide.BUY if delta > 0 else OrderSide.SELL
        if (
            self.order_request.side != expected_side
            or self.order_request.quantity != abs(delta)
        ):
            raise ValueError("transition leg order must match leg delta")
        return self


class ExecutionTransitionPlan(FrozenModel):
    """Immutable semantic transition plan for one execution plan."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    transition_plan_id: str = Field(min_length=1)
    execution_plan_id: str = Field(min_length=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    symbol: str = Field(min_length=1)
    current_quantity: int
    target_quantity: int
    legs: tuple[ExecutionTransitionLeg, ...]
    created_at: datetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_transition_chain(self) -> "ExecutionTransitionPlan":
        if self.current_quantity == self.target_quantity:
            if self.legs:
                raise ValueError("satisfied transition must not have legs")
            return self
        if not self.legs:
            raise ValueError("unsatisfied transition requires legs")
        expected_start = self.current_quantity
        seen_client_ids: set[str] = set()
        for expected_index, leg in enumerate(self.legs, start=1):
            if leg.leg_index != expected_index:
                raise ValueError("transition leg indexes must be contiguous")
            if leg.order_request.symbol != self.symbol:
                raise ValueError("transition leg symbol differs from plan")
            if leg.required_start_quantity != expected_start:
                raise ValueError("transition leg chain is not contiguous")
            if leg.client_order_id in seen_client_ids:
                raise ValueError("transition leg client order IDs must differ")
            seen_client_ids.add(leg.client_order_id)
            expected_start = leg.required_end_quantity
        if expected_start != self.target_quantity:
            raise ValueError("transition legs do not reach target quantity")
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


class ExecutionDryRunObservation(FrozenModel):
    """Immutable read-only evaluation of one claimed execution plan."""

    schema_version: Literal[2] = EXECUTION_LIFECYCLE_SCHEMA_VERSION
    observation_id: str = Field(min_length=1)
    execution_plan_id: str = Field(min_length=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    account_snapshot_id: str = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    broker_environment: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    current_quantity: int
    target_quantity: int
    order_request: OrderRequest | None = None
    reference_price: float
    notional: float = Field(ge=0)
    safety_check: TradingSafetyCheck
    status: ExecutionDryRunStatus
    validation_reasons: tuple[str, ...] = ()
    observed_at: datetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_dry_run_result(self) -> "ExecutionDryRunObservation":
        if self.status == ExecutionDryRunStatus.WOULD_SUBMIT:
            if (
                self.order_request is None
                or self.validation_reasons
                or self.safety_check.mode != TradingMode.DRY_RUN
                or not self.safety_check.allowed
                or self.reference_price <= 0
            ):
                raise ValueError(
                    "would-submit dry-run requires an eligible order"
                )
            if self.notional <= 0:
                raise ValueError("would-submit dry-run requires notional")
        elif self.status == ExecutionDryRunStatus.ALREADY_SATISFIED:
            if (
                self.order_request is not None
                or self.current_quantity != self.target_quantity
                or self.validation_reasons
                or self.safety_check.mode != TradingMode.DRY_RUN
                or not self.safety_check.allowed
                or self.reference_price <= 0
                or self.notional != 0
            ):
                raise ValueError(
                    "already-satisfied dry-run must have no order or reasons"
                )
        elif not self.validation_reasons:
            raise ValueError("blocked dry-run requires validation reasons")
        return self
