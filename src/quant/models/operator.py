"""Define reviewed request and inspection contracts for operator workflows."""

from decimal import Decimal
from enum import StrEnum
from typing import Literal

from pydantic import AwareDatetime, Field, field_validator, model_validator

from quant.models.activation import ActivationEffectiveStatus
from quant.models.autonomous import (
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
)
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


class SupervisedProviderOperatorRequest(FrozenModel):
    """Immutable reviewed request for one local assembly-to-supervisor run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    assembly_manifest_path: str = Field(min_length=1)
    assembly_manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assembly_rehearsal_report_path: str = Field(min_length=1)
    assembly_rehearsal_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    service_policy: SupervisedDryRunServicePolicy
    output_root: str = Field(min_length=1)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator("request_id")
    @classmethod
    def request_id_must_be_safe_path_component(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "supervised provider operator request ID must be safe"
            )
        return value


class SupervisedProviderOperatorRecord(FrozenModel):
    """Immutable result of one local assembly-to-supervisor operator run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assembly_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    service_status: SupervisedDryRunServiceStatus
    assembly_record_path: str = Field(min_length=1)
    assembly_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    service_record_path: str = Field(min_length=1)
    service_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    completed_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()


class SupervisedProviderOperatorRehearsalScenario(StrEnum):
    """Required actual-command supervised-provider rehearsal scenarios."""

    FRESH_COMPLETION = "fresh_completion"
    RESTART_REUSE = "restart_reuse"
    STALE_INPUT_BLOCK = "stale_input_block"
    TAMPERED_INPUT_BLOCK = "tampered_input_block"


class SupervisedProviderOperatorCommandObservation(FrozenModel):
    """Immutable observation of one actual operator command invocation."""

    schema_version: Literal[1] = 1
    observation_id: str = Field(min_length=1)
    scenario: SupervisedProviderOperatorRehearsalScenario
    sequence: int = Field(ge=1)
    executable_path: str = Field(min_length=1)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    arguments: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    stdout: str
    stderr: str
    observed_at: AwareDatetime


class SupervisedProviderOperatorRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one actual-command operator scenario."""

    scenario: SupervisedProviderOperatorRehearsalScenario
    passed: bool
    command_observation_paths: tuple[str, ...] = Field(min_length=1)
    command_observation_sha256s: tuple[str, ...] = Field(min_length=1)
    operator_record_paths: tuple[str, ...] = ()
    operator_record_sha256s: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator(
        "command_observation_paths",
        "operator_record_paths",
        "evidence_paths",
    )
    @classmethod
    def paths_must_be_unique(cls, paths: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(paths)) != len(paths):
            raise ValueError("operator rehearsal evidence paths must be unique")
        return paths

    @model_validator(mode="after")
    def paths_and_hashes_must_align(
        self,
    ) -> "SupervisedProviderOperatorRehearsalScenarioResult":
        if (
            len(self.command_observation_paths)
            != len(self.command_observation_sha256s)
            or len(self.operator_record_paths)
            != len(self.operator_record_sha256s)
            or len(self.evidence_paths) != len(self.evidence_sha256s)
        ):
            raise ValueError("operator rehearsal paths and hashes must align")
        return self


class SupervisedProviderOperatorRehearsalReport(FrozenModel):
    """Immutable actual-command supervised-provider rehearsal report."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evidence_root: str = Field(min_length=1)
    executable_path: str = Field(min_length=1)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_paths: tuple[str, ...] = Field(min_length=1)
    source_sha256s: tuple[str, ...] = Field(min_length=1)
    prerequisite_report_path: str = Field(min_length=1)
    prerequisite_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[SupervisedProviderOperatorRehearsalScenarioResult, ...] = (
        Field(min_length=1)
    )
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_complete_scenarios(
        self,
    ) -> "SupervisedProviderOperatorRehearsalReport":
        if len(self.source_paths) != len(self.source_sha256s):
            raise ValueError("operator rehearsal source paths must align")
        if len(set(self.source_paths)) != len(self.source_paths):
            raise ValueError("operator rehearsal source paths must be unique")
        scenarios = {item.scenario for item in self.scenarios}
        if scenarios != set(
            SupervisedProviderOperatorRehearsalScenario
        ) or len(scenarios) != len(self.scenarios):
            raise ValueError("operator rehearsal must include every scenario")
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError("operator rehearsal passed status must match")
        return self
