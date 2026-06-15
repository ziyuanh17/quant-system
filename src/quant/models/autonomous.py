"""Define bounded authorization and run records for autonomous dry-runs."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from quant.models.base import FrozenModel
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.targets import (
    ContributorSet,
    ResearchRiskPolicy,
    StrategyEvaluation,
    StrategyTargetDecision,
)


class AutonomousDryRunStatus(StrEnum):
    """Outcome of one bounded autonomous dry-run attempt."""

    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"


class AutonomousDryRunAuthorization(FrozenModel):
    """Immutable permission for a bounded series of broker-free dry-runs."""

    schema_version: Literal[1] = 1
    authorization_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    symbol: str = Field(min_length=1)
    contributor_set_id: str = Field(min_length=1)
    contributor_set_revision: int = Field(ge=1)
    allowed_strategies: tuple[tuple[str, str], ...] = Field(min_length=1)
    broker_name: str = Field(min_length=1)
    account_id: str = Field(min_length=1)
    allow_short_targets: bool = False
    max_absolute_target_shares: Decimal = Field(gt=0)
    maximum_runs: int = Field(ge=1)
    minimum_interval_seconds: int = Field(ge=0)
    issued_at: AwareDatetime
    effective_at: AwareDatetime
    valid_until: AwareDatetime
    issued_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_bounds(self) -> "AutonomousDryRunAuthorization":
        if self.effective_at < self.issued_at:
            raise ValueError(
                "authorization cannot be effective before issuance"
            )
        if self.valid_until <= self.effective_at:
            raise ValueError("authorization validity interval must be positive")
        if len(set(self.allowed_strategies)) != len(self.allowed_strategies):
            raise ValueError("allowed strategy identities must be unique")
        return self


class AutonomousDryRunRequest(FrozenModel):
    """Complete broker-free input for one authorized autonomous dry-run."""

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    orchestration_id: str = Field(min_length=1)
    contributor_set: ContributorSet
    strategy_decisions: tuple[StrategyTargetDecision, ...] = Field(min_length=1)
    strategy_evaluations: tuple[StrategyEvaluation, ...] = Field(min_length=1)
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


class AutonomousDryRunRecord(FrozenModel):
    """Immutable outcome of one autonomously authorized dry-run attempt."""

    schema_version: Literal[1] = 1
    run_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    status: AutonomousDryRunStatus
    evaluated_at: datetime
    orchestration_id: str | None = None
    workflow_status: str | None = None
    dry_run_status: str | None = None
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()
