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


class FiniteSupervisedProviderStatus(StrEnum):
    """Terminal status of one finite supervised-provider request list."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


class SupervisedProviderDiscoveryStatus(StrEnum):
    """Terminal status of one reviewed request discovery pass."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


class SupervisedProviderDiscoveryLoopStatus(StrEnum):
    """Terminal status of one discovery-to-loop composition."""

    COMPLETED = "completed"
    BLOCKED = "blocked"


class SupervisedProviderDiscoveryPolicy(FrozenModel):
    """Immutable API-only policy for discovering reviewed request files."""

    schema_version: Literal[1] = 1
    discovery_id: str = Field(min_length=1)
    discovery_policy_version: str = Field(min_length=1)
    request_directory: str = Field(min_length=1)
    request_glob: str = "*.json"
    maximum_requests: int = Field(ge=1)
    finite_loop_id: str = Field(min_length=1)
    finite_output_root: str = Field(min_length=1)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator("discovery_id", "finite_loop_id")
    @classmethod
    def identifiers_must_be_safe_path_components(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "provider discovery IDs must be safe path components"
            )
        return value

    @field_validator("request_glob")
    @classmethod
    def request_glob_must_be_narrow(cls, value: str) -> str:
        if value != "*.json":
            raise ValueError("provider discovery only supports *.json")
        return value


class SupervisedProviderDiscoveryResult(FrozenModel):
    """Immutable result of one API-only reviewed request discovery pass."""

    schema_version: Literal[1] = 1
    discovery_id: str = Field(min_length=1)
    discovery_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: SupervisedProviderDiscoveryStatus
    discovered_at: AwareDatetime
    request_paths: tuple[str, ...] = ()
    request_sha256s: tuple[str, ...] = ()
    finite_manifest_path: str | None = None
    finite_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    blocked_reason: str | None = None
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_must_match_status(
        self,
    ) -> "SupervisedProviderDiscoveryResult":
        if len(self.request_paths) != len(self.request_sha256s):
            raise ValueError("provider discovery request evidence must align")
        if len(set(self.request_paths)) != len(self.request_paths):
            raise ValueError("provider discovery request paths must be unique")
        if (self.finite_manifest_path is None) != (
            self.finite_manifest_sha256 is None
        ):
            raise ValueError("provider discovery manifest evidence must align")
        if self.status == SupervisedProviderDiscoveryStatus.COMPLETED and (
            not self.request_paths
            or self.finite_manifest_path is None
            or self.blocked_reason is not None
        ):
            raise ValueError(
                "completed provider discovery requires manifest evidence"
            )
        if self.status == SupervisedProviderDiscoveryStatus.BLOCKED and (
            self.blocked_reason is None or self.finite_manifest_path is not None
        ):
            raise ValueError(
                "blocked provider discovery requires only a blocked reason"
            )
        return self


class SupervisedProviderDiscoveryOperatorRequest(FrozenModel):
    """Immutable reviewed request for one discovery-only operator run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    discovery_policy: SupervisedProviderDiscoveryPolicy
    output_root: str = Field(min_length=1)
    discovery_rehearsal_report_path: str = Field(min_length=1)
    discovery_rehearsal_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator("request_id")
    @classmethod
    def request_id_must_be_safe_path_component(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "supervised provider discovery operator request ID must be safe"
            )
        return value


class SupervisedProviderDiscoveryOperatorRecord(FrozenModel):
    """Immutable result of one discovery-only operator run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery_id: str = Field(min_length=1)
    discovery_status: SupervisedProviderDiscoveryStatus
    discovery_result_path: str = Field(min_length=1)
    discovery_result_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finite_manifest_path: str | None = None
    finite_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    completed_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def manifest_evidence_must_align(
        self,
    ) -> "SupervisedProviderDiscoveryOperatorRecord":
        if (self.finite_manifest_path is None) != (
            self.finite_manifest_sha256 is None
        ):
            raise ValueError(
                "discovery operator manifest evidence must align"
            )
        return self


class SupervisedProviderDiscoveryLoopOperatorRequest(FrozenModel):
    """Immutable reviewed request for one discovery-to-loop composition."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    discovery_operator_request_path: str = Field(min_length=1)
    discovery_operator_request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    discovery_operator_rehearsal_report_path: str = Field(min_length=1)
    discovery_operator_rehearsal_report_sha256: str = Field(
        pattern=r"^[0-9a-f]{64}$"
    )
    output_root: str = Field(min_length=1)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator("request_id")
    @classmethod
    def request_id_must_be_safe_path_component(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "supervised provider discovery-loop request ID must be safe"
            )
        return value


class SupervisedProviderDiscoveryLoopOperatorRecord(FrozenModel):
    """Immutable result of one discovery-to-loop composition."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    request_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: SupervisedProviderDiscoveryLoopStatus
    discovery_operator_record_path: str = Field(min_length=1)
    discovery_operator_record_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    finite_manifest_path: str | None = None
    finite_manifest_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    finite_loop_record_path: str | None = None
    finite_loop_record_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    completed_at: AwareDatetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_must_match_status(
        self,
    ) -> "SupervisedProviderDiscoveryLoopOperatorRecord":
        if (self.finite_manifest_path is None) != (
            self.finite_manifest_sha256 is None
        ):
            raise ValueError(
                "discovery-loop manifest evidence must align"
            )
        if (self.finite_loop_record_path is None) != (
            self.finite_loop_record_sha256 is None
        ):
            raise ValueError(
                "discovery-loop finite record evidence must align"
            )
        if (
            self.status == SupervisedProviderDiscoveryLoopStatus.COMPLETED
            and self.finite_loop_record_path is None
        ):
            raise ValueError(
                "completed discovery-loop composition requires loop record"
            )
        if (
            self.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED
            and self.reason == "completed"
        ):
            raise ValueError("blocked discovery-loop requires blocked reason")
        return self


class FiniteSupervisedProviderManifest(FrozenModel):
    """Immutable ordered list of fresh supervised-provider requests."""

    schema_version: Literal[1] = 1
    loop_id: str = Field(min_length=1)
    request_paths: tuple[str, ...] = Field(min_length=1)
    request_sha256s: tuple[str, ...] = Field(min_length=1)
    output_root: str = Field(min_length=1)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator("loop_id")
    @classmethod
    def loop_id_must_be_safe_path_component(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError("finite supervised-provider loop ID must be safe")
        return value

    @model_validator(mode="after")
    def request_paths_and_hashes_must_align(
        self,
    ) -> "FiniteSupervisedProviderManifest":
        if len(self.request_paths) != len(self.request_sha256s):
            raise ValueError(
                "finite provider request paths and hashes must align"
            )
        if len(set(self.request_paths)) != len(self.request_paths):
            raise ValueError("finite provider request paths must be unique")
        return self


class FiniteSupervisedProviderRecord(FrozenModel):
    """Immutable summary of one finite supervised-provider request list."""

    schema_version: Literal[1] = 1
    loop_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    status: FiniteSupervisedProviderStatus
    requested_count: int = Field(ge=1)
    completed_request_ids: tuple[str, ...] = ()
    operator_record_paths: tuple[str, ...] = ()
    operator_record_sha256s: tuple[str, ...] = ()
    blocked_request_id: str | None = None
    blocked_operator_record_path: str | None = None
    blocked_operator_record_sha256: str | None = Field(
        default=None, pattern=r"^[0-9a-f]{64}$"
    )
    started_at: AwareDatetime
    completed_at: AwareDatetime
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_must_match_status(self) -> "FiniteSupervisedProviderRecord":
        if not (
            len(self.completed_request_ids)
            == len(self.operator_record_paths)
            == len(self.operator_record_sha256s)
        ):
            raise ValueError("finite provider completed evidence must align")
        if len(self.completed_request_ids) > self.requested_count:
            raise ValueError("finite provider loop completed extra requests")
        if len(set(self.completed_request_ids)) != len(
            self.completed_request_ids
        ):
            raise ValueError(
                "finite provider completed request IDs must be unique"
            )
        if self.status == FiniteSupervisedProviderStatus.COMPLETED and (
            len(self.completed_request_ids) != self.requested_count
            or self.blocked_request_id is not None
        ):
            raise ValueError(
                "completed finite provider loop must finish all work"
            )
        if (
            self.status == FiniteSupervisedProviderStatus.BLOCKED
            and self.blocked_request_id is None
        ):
            raise ValueError("blocked finite provider loop requires request ID")
        if self.status == FiniteSupervisedProviderStatus.BLOCKED and (
            len(self.completed_request_ids) >= self.requested_count
            or self.blocked_request_id in self.completed_request_ids
        ):
            raise ValueError("blocked finite provider loop must stop early")
        if (self.blocked_operator_record_path is None) != (
            self.blocked_operator_record_sha256 is None
        ):
            raise ValueError("blocked finite provider evidence must align")
        return self


class SupervisedProviderOperatorRehearsalScenario(StrEnum):
    """Required actual-command supervised-provider rehearsal scenarios."""

    FRESH_COMPLETION = "fresh_completion"
    RESTART_REUSE = "restart_reuse"
    STALE_INPUT_BLOCK = "stale_input_block"
    TAMPERED_INPUT_BLOCK = "tampered_input_block"


class FiniteSupervisedProviderRehearsalScenario(StrEnum):
    """Required actual-command finite supervised-provider scenarios."""

    EXACT_LIST_COMPLETION = "exact_list_completion"
    RESTART_REUSE = "restart_reuse"
    PREFLIGHT_REJECTION = "preflight_rejection"
    STOP_ON_BLOCK = "stop_on_block"


class SupervisedProviderDiscoveryRehearsalScenario(StrEnum):
    """Required no-network supervised-provider discovery scenarios."""

    DISCOVERY_TO_LOOP = "discovery_to_loop"
    RESTART_REUSE = "restart_reuse"
    EMPTY_DIRECTORY_BLOCK = "empty_directory_block"
    OVER_LIMIT_BLOCK = "over_limit_block"
    CHANGED_INPUT_BLOCK = "changed_input_block"
    STOP_ON_BLOCK_HANDOFF = "stop_on_block_handoff"


class SupervisedProviderDiscoveryOperatorRehearsalScenario(StrEnum):
    """Required actual-command discovery operator rehearsal scenarios."""

    FRESH_COMPLETION = "fresh_completion"
    RESTART_REUSE = "restart_reuse"
    BLOCKED_DISCOVERY = "blocked_discovery"
    TAMPERED_REHEARSAL_BLOCK = "tampered_rehearsal_block"


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


class FiniteSupervisedProviderCommandObservation(FrozenModel):
    """Immutable observation of one actual finite-provider command."""

    schema_version: Literal[1] = 1
    observation_id: str = Field(min_length=1)
    scenario: FiniteSupervisedProviderRehearsalScenario
    sequence: int = Field(ge=1)
    executable_path: str = Field(min_length=1)
    executable_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    arguments: tuple[str, ...] = Field(min_length=1)
    exit_code: int
    stdout: str
    stderr: str
    observed_at: AwareDatetime


class SupervisedProviderDiscoveryOperatorCommandObservation(FrozenModel):
    """Immutable observation of one discovery operator command."""

    schema_version: Literal[1] = 1
    observation_id: str = Field(min_length=1)
    scenario: SupervisedProviderDiscoveryOperatorRehearsalScenario
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


class FiniteSupervisedProviderRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one finite actual-command scenario."""

    scenario: FiniteSupervisedProviderRehearsalScenario
    passed: bool
    command_observation_paths: tuple[str, ...] = Field(min_length=1)
    command_observation_sha256s: tuple[str, ...] = Field(min_length=1)
    loop_record_paths: tuple[str, ...] = ()
    loop_record_sha256s: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def paths_and_hashes_must_align(
        self,
    ) -> "FiniteSupervisedProviderRehearsalScenarioResult":
        if (
            len(self.command_observation_paths)
            != len(self.command_observation_sha256s)
            or len(self.loop_record_paths) != len(self.loop_record_sha256s)
            or len(self.evidence_paths) != len(self.evidence_sha256s)
        ):
            raise ValueError("finite rehearsal paths and hashes must align")
        return self


class SupervisedProviderDiscoveryRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one discovery handoff rehearsal scenario."""

    scenario: SupervisedProviderDiscoveryRehearsalScenario
    passed: bool
    discovery_result_paths: tuple[str, ...] = Field(min_length=1)
    discovery_result_sha256s: tuple[str, ...] = Field(min_length=1)
    finite_manifest_paths: tuple[str, ...] = ()
    finite_manifest_sha256s: tuple[str, ...] = ()
    loop_record_paths: tuple[str, ...] = ()
    loop_record_sha256s: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def paths_and_hashes_must_align(
        self,
    ) -> "SupervisedProviderDiscoveryRehearsalScenarioResult":
        if (
            len(self.discovery_result_paths)
            != len(self.discovery_result_sha256s)
            or len(self.finite_manifest_paths)
            != len(self.finite_manifest_sha256s)
            or len(self.loop_record_paths) != len(self.loop_record_sha256s)
            or len(self.evidence_paths) != len(self.evidence_sha256s)
        ):
            raise ValueError("discovery rehearsal paths and hashes must align")
        return self


class SupervisedProviderDiscoveryOperatorRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one discovery operator command scenario."""

    scenario: SupervisedProviderDiscoveryOperatorRehearsalScenario
    passed: bool
    command_observation_paths: tuple[str, ...] = Field(min_length=1)
    command_observation_sha256s: tuple[str, ...] = Field(min_length=1)
    operator_record_paths: tuple[str, ...] = ()
    operator_record_sha256s: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    evidence_sha256s: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def paths_and_hashes_must_align(
        self,
    ) -> "SupervisedProviderDiscoveryOperatorRehearsalScenarioResult":
        if (
            len(self.command_observation_paths)
            != len(self.command_observation_sha256s)
            or len(self.operator_record_paths)
            != len(self.operator_record_sha256s)
            or len(self.evidence_paths) != len(self.evidence_sha256s)
        ):
            raise ValueError(
                "discovery operator rehearsal paths and hashes must align"
            )
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
        if scenarios != set(SupervisedProviderOperatorRehearsalScenario) or len(
            scenarios
        ) != len(self.scenarios):
            raise ValueError("operator rehearsal must include every scenario")
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError("operator rehearsal passed status must match")
        return self


class FiniteSupervisedProviderRehearsalReport(FrozenModel):
    """Immutable actual-command finite supervised-provider rehearsal report."""

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
    scenarios: tuple[FiniteSupervisedProviderRehearsalScenarioResult, ...] = (
        Field(min_length=1)
    )
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_complete_scenarios(
        self,
    ) -> "FiniteSupervisedProviderRehearsalReport":
        if len(self.source_paths) != len(self.source_sha256s):
            raise ValueError("finite rehearsal source paths must align")
        if len(set(self.source_paths)) != len(self.source_paths):
            raise ValueError("finite rehearsal source paths must be unique")
        scenarios = {item.scenario for item in self.scenarios}
        if scenarios != set(FiniteSupervisedProviderRehearsalScenario) or len(
            scenarios
        ) != len(self.scenarios):
            raise ValueError("finite rehearsal must include every scenario")
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError("finite rehearsal passed status must match")
        return self


class SupervisedProviderDiscoveryRehearsalReport(FrozenModel):
    """Immutable no-network supervised-provider discovery rehearsal report."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evidence_root: str = Field(min_length=1)
    source_paths: tuple[str, ...] = Field(min_length=1)
    source_sha256s: tuple[str, ...] = Field(min_length=1)
    prerequisite_report_path: str = Field(min_length=1)
    prerequisite_report_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[
        SupervisedProviderDiscoveryRehearsalScenarioResult, ...
    ] = Field(min_length=1)
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_complete_scenarios(
        self,
    ) -> "SupervisedProviderDiscoveryRehearsalReport":
        if len(self.source_paths) != len(self.source_sha256s):
            raise ValueError("discovery rehearsal source paths must align")
        if len(set(self.source_paths)) != len(self.source_paths):
            raise ValueError("discovery rehearsal source paths must be unique")
        scenarios = {item.scenario for item in self.scenarios}
        if scenarios != set(
            SupervisedProviderDiscoveryRehearsalScenario
        ) or len(scenarios) != len(self.scenarios):
            raise ValueError(
                "discovery rehearsal must include every scenario"
            )
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError("discovery rehearsal passed status must match")
        return self


class SupervisedProviderDiscoveryOperatorRehearsalReport(FrozenModel):
    """Immutable actual-command discovery operator rehearsal report."""

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
    scenarios: tuple[
        SupervisedProviderDiscoveryOperatorRehearsalScenarioResult, ...
    ] = Field(min_length=1)
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_complete_scenarios(
        self,
    ) -> "SupervisedProviderDiscoveryOperatorRehearsalReport":
        if len(self.source_paths) != len(self.source_sha256s):
            raise ValueError(
                "discovery operator rehearsal source paths must align"
            )
        if len(set(self.source_paths)) != len(self.source_paths):
            raise ValueError(
                "discovery operator rehearsal source paths must be unique"
            )
        scenarios = {item.scenario for item in self.scenarios}
        if scenarios != set(
            SupervisedProviderDiscoveryOperatorRehearsalScenario
        ) or len(scenarios) != len(self.scenarios):
            raise ValueError(
                "discovery operator rehearsal must include every scenario"
            )
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError(
                "discovery operator rehearsal passed status must match"
            )
        return self
