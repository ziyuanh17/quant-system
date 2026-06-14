"""Define semantic-target activation authorization and consumption models."""

from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, model_validator

from quant.models.base import FrozenModel


class SemanticTargetActivationScope(StrEnum):
    DRY_RUN = "dry_run"
    SEMANTIC_PAPER = "semantic_paper"
    ALPACA_PAPER = "alpaca_paper"


class ActivationEffectiveStatus(StrEnum):
    ACTIVE = "active"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"


class ActivationDecision(StrEnum):
    ALLOWED = "allowed"
    BLOCKED = "blocked"


class SemanticTargetActivationAuthorization(FrozenModel):
    """Immutable human authorization for a bounded operational capability."""

    schema_version: Literal[1] = 1
    authorization_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    allowed_scopes: tuple[SemanticTargetActivationScope, ...] = Field(
        min_length=1
    )
    orchestration_policy_version: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    rehearsal_id: str = Field(min_length=1)
    rehearsal_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issued_at: AwareDatetime
    effective_at: AwareDatetime
    valid_until: AwareDatetime
    issued_by: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_interval_and_scopes(
        self,
    ) -> "SemanticTargetActivationAuthorization":
        if self.effective_at < self.issued_at:
            raise ValueError("activation cannot be effective before issuance")
        if self.valid_until <= self.effective_at:
            raise ValueError("activation validity interval must be positive")
        if len(set(self.allowed_scopes)) != len(self.allowed_scopes):
            raise ValueError("activation scopes must be unique")
        return self


class SemanticTargetActivationEvaluation(FrozenModel):
    """Append-only evidence from evaluating one activation request."""

    schema_version: Literal[1] = 1
    evaluation_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    requested_scope: SemanticTargetActivationScope
    evaluated_at: AwareDatetime
    effective_status: ActivationEffectiveStatus
    decision: ActivationDecision
    rehearsal_id: str = Field(min_length=1)
    rehearsal_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    issues: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = Field(min_length=1)

    @model_validator(mode="after")
    def decision_must_match_issues(
        self,
    ) -> "SemanticTargetActivationEvaluation":
        if self.decision == ActivationDecision.ALLOWED and self.issues:
            raise ValueError(
                "allowed activation evaluations cannot have issues"
            )
        if self.decision == ActivationDecision.BLOCKED and not self.issues:
            raise ValueError("blocked activation evaluations require issues")
        return self


class SemanticTargetActivationConsumption(FrozenModel):
    """Immutable binding of one activation evaluation to one orchestration."""

    schema_version: Literal[1] = 1
    consumption_id: str = Field(min_length=1)
    orchestration_id: str = Field(min_length=1)
    requested_scope: SemanticTargetActivationScope
    activation_evaluation_id: str = Field(min_length=1)
    activation_decision: ActivationDecision
    consumed_at: AwareDatetime
    activation_evaluation_path: str = Field(min_length=1)
    reason: str = Field(min_length=1)
