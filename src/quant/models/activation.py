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


class ActivationConsumptionRehearsalScenario(StrEnum):
    DRY_RUN_RESTART = "dry_run_restart"
    LOCAL_PAPER_RESTART = "local_paper_restart"
    EXPIRED_AUTHORIZATION_BLOCK = "expired_authorization_block"
    SCOPE_MISMATCH_BLOCK = "scope_mismatch_block"
    SINGLE_CONSUMPTION_ENFORCEMENT = "single_consumption_enforcement"


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


class ActivationConsumptionRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one activation-consumption rehearsal scenario."""

    scenario: ActivationConsumptionRehearsalScenario
    passed: bool
    activation_decisions: tuple[ActivationDecision, ...] = Field(min_length=1)
    evaluation_ids: tuple[str, ...] = Field(min_length=1)
    evaluation_paths: tuple[str, ...] = Field(min_length=1)
    consumption_ids: tuple[str, ...] = Field(min_length=1)
    consumption_paths: tuple[str, ...] = Field(min_length=1)
    workflow_orchestration_ids: tuple[str, ...] = ()
    workflow_statuses: tuple[str, ...] = ()
    workflow_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_sequences_must_align(
        self,
    ) -> "ActivationConsumptionRehearsalScenarioResult":
        count = len(self.activation_decisions)
        if (
            len(self.evaluation_ids) != count
            or len(self.evaluation_paths) != count
            or len(self.consumption_ids) != count
            or len(self.consumption_paths) != count
        ):
            raise ValueError("activation rehearsal evidence must align")
        if (
            len(self.workflow_orchestration_ids) != len(self.workflow_paths)
            or len(self.workflow_statuses) != len(self.workflow_paths)
        ):
            raise ValueError(
                "activation rehearsal workflow evidence must align"
            )
        return self


class ActivationConsumptionRehearsalReport(FrozenModel):
    """Immutable second-layer rehearsal report for activation consumption."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    base_rehearsal_id: str = Field(min_length=1)
    base_rehearsal_report_path: str = Field(min_length=1)
    base_rehearsal_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[ActivationConsumptionRehearsalScenarioResult, ...] = Field(
        min_length=1
    )
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_scenarios(
        self,
    ) -> "ActivationConsumptionRehearsalReport":
        if self.passed != all(item.passed for item in self.scenarios):
            raise ValueError("activation rehearsal passed status must match")
        if len({item.scenario for item in self.scenarios}) != len(
            self.scenarios
        ):
            raise ValueError("activation rehearsal scenarios must be unique")
        return self
