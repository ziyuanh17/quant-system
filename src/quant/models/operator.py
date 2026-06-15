"""Define reviewed request and inspection contracts for operator workflows."""

from decimal import Decimal
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from quant.models.activation import ActivationEffectiveStatus
from quant.models.base import FrozenModel
from quant.models.execution import LiveAccountSnapshot, OrderSide
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.targets import ResearchRiskPolicy


class ActivatedDryRunOperatorRequest(FrozenModel):
    """Immutable reviewed request for one activated semantic-target dry-run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    activation_evaluation_id: str = Field(min_length=1)
    orchestration_id: str = Field(min_length=1)
    authorization_path: str = Field(min_length=1)
    rehearsal_report_path: str = Field(min_length=1)
    activation_consumption_rehearsal_report_path: str = Field(min_length=1)
    contributor_set_path: str = Field(min_length=1)
    strategy_decision_paths: tuple[str, ...] = Field(min_length=1)
    strategy_evaluation_paths: tuple[str, ...] = Field(min_length=1)
    risk_policy: ResearchRiskPolicy
    portfolio_target_id: str = Field(min_length=1)
    portfolio_target_revision: int = Field(ge=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    account: LiveAccountSnapshot
    execution_policy: ExecutionLifecyclePolicy
    reference_price: float = Field(gt=0)
    evaluated_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator(
        "request_id", "activation_evaluation_id", "orchestration_id"
    )
    @classmethod
    def identifiers_must_be_safe_path_components(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "operator request IDs must be safe path components"
            )
        return value

    @field_validator("strategy_decision_paths", "strategy_evaluation_paths")
    @classmethod
    def artifact_paths_must_be_unique(
        cls, paths: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(set(paths)) != len(paths):
            raise ValueError("operator request artifact paths must be unique")
        return paths


class ActivatedDryRunRequestInspection(FrozenModel):
    """Read-only explanation of one activated dry-run operator request."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    inspected_at: AwareDatetime
    valid_now: bool
    issues: tuple[str, ...] = ()
    symbol: str | None = None
    current_quantity: int | None = None
    approved_target_quantity: Decimal | None = None
    intended_order_side: OrderSide | None = None
    intended_order_quantity: int | None = Field(default=None, gt=0)
    intended_order_notional: float | None = Field(default=None, ge=0)
    reference_price: float = Field(gt=0)
    authorization_id: str | None = None
    authorization_effective_status: ActivationEffectiveStatus | None = None
    authorization_valid_until: AwareDatetime | None = None
    base_rehearsal_passed: bool = False
    activation_consumption_rehearsal_passed: bool = False
    summary: str = Field(min_length=1)
