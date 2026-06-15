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


class SupervisedDryRunHealthStatus(StrEnum):
    """Health decision made immediately before one supervised cycle."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class SupervisedDryRunCycleOutcome(StrEnum):
    """Durable outcome of one supervised service cycle."""

    SUCCEEDED = "succeeded"
    BLOCKED = "blocked"
    HEALTH_STOP = "health_stop"
    SHUTDOWN_STOP = "shutdown_stop"
    RUNTIME_STOP = "runtime_stop"
    ERROR_STOP = "error_stop"


class SupervisedDryRunServiceStatus(StrEnum):
    """Final state of one bounded supervised service invocation."""

    COMPLETED = "completed"
    STOPPED = "stopped"


class SupervisedProviderComponentStatus(StrEnum):
    """Reported state of one required supervised-service input component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"


class AutonomousDryRunRehearsalScenario(StrEnum):
    """Required no-network autonomous dry-run rehearsal scenarios."""

    REPEATED_ALLOWED_RUNS = "repeated_allowed_runs"
    RESTART_IDEMPOTENCY = "restart_idempotency"
    EXPIRED_AUTHORIZATION_BLOCK = "expired_authorization_block"
    TARGET_LIMIT_BLOCK = "target_limit_block"
    HALT_AFTER_BLOCK = "halt_after_block"


class SupervisedDryRunRehearsalScenario(StrEnum):
    """Required no-network supervised-service rehearsal scenarios."""

    HEALTHY_CONTINUATION = "healthy_continuation"
    DEGRADED_HEALTH_STOP = "degraded_health_stop"
    FAILED_HEALTH_STOP = "failed_health_stop"
    EXPLICIT_SHUTDOWN_STOP = "explicit_shutdown_stop"
    BLOCKED_RUN_STOP = "blocked_run_stop"
    PROVIDER_ERROR_STOP = "provider_error_stop"
    RUNTIME_BOUND_STOP = "runtime_bound_stop"
    RESTART_CONTINUATION = "restart_continuation"


class SupervisedProviderAssemblyRehearsalScenario(StrEnum):
    """Required no-network provider-assembly rehearsal scenarios."""

    SUCCESSFUL_ASSEMBLY = "successful_assembly"
    RESTART_REUSE = "restart_reuse"
    CHANGED_INPUT_REJECTED = "changed_input_rejected"
    CHANGED_OUTPUT_DETECTED = "changed_output_detected"
    STALE_TARGET_REJECTED = "stale_target_rejected"
    STALE_ACCOUNT_REJECTED = "stale_account_rejected"
    PROVIDER_TO_SUPERVISOR = "provider_to_supervisor"


class SupervisedProviderAssemblyRehearsalOutcome(StrEnum):
    """Observed result of one provider-assembly rehearsal scenario."""

    ASSEMBLED = "assembled"
    REJECTED = "rejected"
    SUPERVISOR_COMPLETED = "supervisor_completed"


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


class AutonomousDryRunLoopManifest(FrozenModel):
    """Immutable finite input list for one manually started dry-run loop."""

    schema_version: Literal[1] = 1
    loop_id: str = Field(min_length=1)
    authorization_path: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_paths: tuple[str, ...] = Field(min_length=1)
    request_sha256s: tuple[str, ...] = Field(min_length=1)
    interval_seconds: float = Field(ge=0)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def request_paths_must_be_unique(self) -> "AutonomousDryRunLoopManifest":
        if len(set(self.request_paths)) != len(self.request_paths):
            raise ValueError("finite-loop request paths must be unique")
        if len(self.request_paths) != len(self.request_sha256s):
            raise ValueError("finite-loop request paths and hashes must align")
        return self


class AutonomousDryRunLoopRecord(FrozenModel):
    """Immutable summary of one finite manually started autonomous loop."""

    schema_version: Literal[1] = 1
    loop_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    status: AutonomousDryRunStatus
    requested_run_count: int = Field(ge=1)
    completed_run_ids: tuple[str, ...] = ()
    run_statuses: tuple[AutonomousDryRunStatus, ...] = ()
    started_at: AwareDatetime
    completed_at: AwareDatetime
    stopped_early: bool
    reason: str = Field(min_length=1)
    run_record_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def run_evidence_must_align(self) -> "AutonomousDryRunLoopRecord":
        if not (
            len(self.completed_run_ids)
            == len(self.run_statuses)
            == len(self.run_record_paths)
        ):
            raise ValueError("finite-loop run evidence must align")
        if len(self.completed_run_ids) > self.requested_run_count:
            raise ValueError("finite loop cannot complete extra requests")
        return self


class SupervisedDryRunServicePolicy(FrozenModel):
    """Immutable bounds for one API-only supervised dry-run service."""

    schema_version: Literal[1] = 1
    service_id: str = Field(min_length=1)
    policy_version: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    maximum_cycles: int = Field(ge=1)
    interval_seconds: float = Field(ge=0)
    maximum_runtime_seconds: float = Field(gt=0)
    created_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()


class SupervisedProviderPolicy(FrozenModel):
    """Versioned validity rules for health and fresh-request providers."""

    schema_version: Literal[1] = 1
    provider_policy_version: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    health_source_id: str = Field(min_length=1)
    health_source_version: str = Field(min_length=1)
    request_source_id: str = Field(min_length=1)
    request_source_version: str = Field(min_length=1)
    required_health_components: tuple[str, ...] = Field(min_length=1)
    maximum_health_age_seconds: int = Field(gt=0)
    maximum_request_age_seconds: int = Field(gt=0)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def required_components_are_unique(self) -> "SupervisedProviderPolicy":
        if len(set(self.required_health_components)) != len(
            self.required_health_components
        ):
            raise ValueError("required health components must be unique")
        return self


class SupervisedHealthComponentObservation(FrozenModel):
    """Immutable observation of one required provider health component."""

    schema_version: Literal[1] = 1
    component_id: str = Field(min_length=1)
    status: SupervisedProviderComponentStatus
    observed_at: AwareDatetime
    valid_until: AwareDatetime
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validity_interval_is_positive(
        self,
    ) -> "SupervisedHealthComponentObservation":
        if self.valid_until <= self.observed_at:
            raise ValueError(
                "health component validity interval must be positive"
            )
        return self


class SupervisedHealthSnapshot(FrozenModel):
    """Complete immutable health-source input for one supervised cycle."""

    schema_version: Literal[1] = 1
    snapshot_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=1)
    health_source_id: str = Field(min_length=1)
    health_source_version: str = Field(min_length=1)
    generated_at: AwareDatetime
    components: tuple[SupervisedHealthComponentObservation, ...] = Field(
        min_length=1
    )
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def components_are_unique(self) -> "SupervisedHealthSnapshot":
        component_ids = tuple(item.component_id for item in self.components)
        if len(set(component_ids)) != len(component_ids):
            raise ValueError("health snapshot components must be unique")
        if any(
            item.observed_at > self.generated_at for item in self.components
        ):
            raise ValueError("health snapshot cannot predate its observations")
        return self


class SupervisedRequestEnvelope(FrozenModel):
    """Immutable source envelope for one fresh autonomous dry-run request."""

    schema_version: Literal[1] = 1
    envelope_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=1)
    request_source_id: str = Field(min_length=1)
    request_source_version: str = Field(min_length=1)
    generated_at: AwareDatetime
    valid_until: AwareDatetime
    request: AutonomousDryRunRequest
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validity_interval_is_positive(self) -> "SupervisedRequestEnvelope":
        if self.valid_until <= self.generated_at:
            raise ValueError(
                "request envelope validity interval must be positive"
            )
        return self


class SupervisedProviderAssemblyManifest(FrozenModel):
    """Content-bound inputs for one local no-network provider assembly."""

    schema_version: Literal[1] = 1
    assembly_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=1)
    provider_policy_path: str = Field(min_length=1)
    provider_policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_path: str = Field(min_length=1)
    authorization_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    contributor_set_path: str = Field(min_length=1)
    contributor_set_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    strategy_decision_paths: tuple[str, ...] = Field(min_length=1)
    strategy_decision_sha256s: tuple[str, ...] = Field(min_length=1)
    strategy_evaluation_paths: tuple[str, ...] = Field(min_length=1)
    strategy_evaluation_sha256s: tuple[str, ...] = Field(min_length=1)
    risk_policy: ResearchRiskPolicy
    portfolio_target_id: str = Field(min_length=1)
    portfolio_target_revision: int = Field(ge=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    account: LiveAccountSnapshot
    execution_policy: ExecutionLifecyclePolicy
    reference_price: float = Field(gt=0)
    generated_at: AwareDatetime
    valid_until: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def paths_and_hashes_align(self) -> "SupervisedProviderAssemblyManifest":
        if len(self.strategy_decision_paths) != len(
            self.strategy_decision_sha256s
        ):
            raise ValueError("strategy decision paths and hashes must align")
        if len(self.strategy_evaluation_paths) != len(
            self.strategy_evaluation_sha256s
        ):
            raise ValueError("strategy evaluation paths and hashes must align")
        if len(set(self.strategy_decision_paths)) != len(
            self.strategy_decision_paths
        ):
            raise ValueError("strategy decision paths must be unique")
        if len(set(self.strategy_evaluation_paths)) != len(
            self.strategy_evaluation_paths
        ):
            raise ValueError("strategy evaluation paths must be unique")
        if self.valid_until <= self.generated_at:
            raise ValueError("assembly validity interval must be positive")
        return self


class SupervisedProviderAssemblyRecord(FrozenModel):
    """Immutable result linking one local provider assembly."""

    schema_version: Literal[1] = 1
    assembly_id: str = Field(min_length=1)
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    service_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=1)
    health_snapshot_id: str = Field(min_length=1)
    request_envelope_id: str = Field(min_length=1)
    health_snapshot_path: str = Field(min_length=1)
    health_snapshot_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    request_envelope_path: str = Field(min_length=1)
    request_envelope_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    assembled_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()


class SupervisedProviderAssemblyRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one provider-assembly rehearsal scenario."""

    scenario: SupervisedProviderAssemblyRehearsalScenario
    passed: bool
    outcome: SupervisedProviderAssemblyRehearsalOutcome
    assembly_record_paths: tuple[str, ...] = ()
    service_record_paths: tuple[str, ...] = ()
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    reason: str = Field(min_length=1)


class SupervisedProviderAssemblyRehearsalReport(FrozenModel):
    """Immutable report for the local provider-assembly rehearsal."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evidence_root: str = Field(min_length=1)
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[SupervisedProviderAssemblyRehearsalScenarioResult, ...] = (
        Field(min_length=1)
    )
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_evidence(
        self,
    ) -> "SupervisedProviderAssemblyRehearsalReport":
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError(
                "provider-assembly rehearsal passed status must match"
            )
        if len({item.scenario for item in self.scenarios}) != len(
            self.scenarios
        ):
            raise ValueError(
                "provider-assembly rehearsal scenarios must be unique"
            )
        if {item.scenario for item in self.scenarios} != set(
            SupervisedProviderAssemblyRehearsalScenario
        ):
            raise ValueError(
                "provider-assembly rehearsal must include every scenario"
            )
        return self


class SupervisedDryRunHealthCheck(FrozenModel):
    """Immutable health decision for one supervised service cycle."""

    schema_version: Literal[1] = 1
    check_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    cycle_index: int = Field(ge=1)
    status: SupervisedDryRunHealthStatus
    checked_at: AwareDatetime
    reasons: tuple[str, ...] = ()
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def unhealthy_checks_explain_reason(
        self,
    ) -> "SupervisedDryRunHealthCheck":
        if (
            self.status != SupervisedDryRunHealthStatus.HEALTHY
            and not self.reasons
        ):
            raise ValueError("unhealthy supervised checks require a reason")
        return self


class SupervisedDryRunCycleEvent(FrozenModel):
    """Append-only evidence for one supervised check-and-run cycle."""

    schema_version: Literal[1] = 1
    event_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    sequence: int = Field(ge=1)
    cycle_index: int = Field(ge=1)
    occurred_at: AwareDatetime
    outcome: SupervisedDryRunCycleOutcome
    reason: str = Field(min_length=1)
    health_check_id: str | None = None
    run_id: str | None = None
    run_status: AutonomousDryRunStatus | None = None
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def run_evidence_matches_outcome(self) -> "SupervisedDryRunCycleEvent":
        run_outcomes = {
            SupervisedDryRunCycleOutcome.SUCCEEDED,
            SupervisedDryRunCycleOutcome.BLOCKED,
        }
        if self.outcome in run_outcomes:
            if (
                self.health_check_id is None
                or self.run_id is None
                or self.run_status is None
            ):
                raise ValueError(
                    "run cycle events require health and run evidence"
                )
            expected = (
                AutonomousDryRunStatus.SUCCEEDED
                if self.outcome == SupervisedDryRunCycleOutcome.SUCCEEDED
                else AutonomousDryRunStatus.BLOCKED
            )
            if self.run_status != expected:
                raise ValueError("run cycle outcome and run status must match")
        elif self.run_id is not None or self.run_status is not None:
            raise ValueError("stop events cannot claim a completed run")
        if (
            self.outcome == SupervisedDryRunCycleOutcome.HEALTH_STOP
            and self.health_check_id is None
        ):
            raise ValueError("health-stop event requires a health check")
        return self


class SupervisedDryRunServiceRecord(FrozenModel):
    """Immutable final summary of one bounded supervised dry-run service."""

    schema_version: Literal[1] = 1
    service_id: str = Field(min_length=1)
    policy_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    authorization_id: str = Field(min_length=1)
    authorization_revision: int = Field(ge=1)
    status: SupervisedDryRunServiceStatus
    completed_cycles: int = Field(ge=0)
    started_at: AwareDatetime
    completed_at: AwareDatetime
    reason: str = Field(min_length=1)
    cycle_event_paths: tuple[str, ...] = ()
    run_ids: tuple[str, ...] = ()

    @model_validator(mode="after")
    def evidence_counts_are_consistent(
        self,
    ) -> "SupervisedDryRunServiceRecord":
        if self.completed_cycles > len(self.run_ids):
            raise ValueError("completed cycles cannot exceed recorded runs")
        if len(self.run_ids) > len(self.cycle_event_paths):
            raise ValueError("recorded runs cannot exceed cycle events")
        return self


class SupervisedDryRunRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one supervised-service rehearsal scenario."""

    scenario: SupervisedDryRunRehearsalScenario
    passed: bool
    service_id: str = Field(min_length=1)
    service_status: SupervisedDryRunServiceStatus
    cycle_outcomes: tuple[SupervisedDryRunCycleOutcome, ...] = Field(
        min_length=1
    )
    service_record_path: str = Field(min_length=1)
    cycle_event_paths: tuple[str, ...] = Field(min_length=1)
    health_check_paths: tuple[str, ...] = ()
    run_record_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def cycle_evidence_must_align(
        self,
    ) -> "SupervisedDryRunRehearsalScenarioResult":
        if len(self.cycle_outcomes) != len(self.cycle_event_paths):
            raise ValueError("supervised rehearsal cycle evidence must align")
        return self


class SupervisedDryRunRehearsalReport(FrozenModel):
    """Immutable report for a no-network supervised-service rehearsal."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evidence_root: str = Field(min_length=1)
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[SupervisedDryRunRehearsalScenarioResult, ...] = Field(
        min_length=1
    )
    prohibited_artifact_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_evidence(
        self,
    ) -> "SupervisedDryRunRehearsalReport":
        expected = (
            all(item.passed for item in self.scenarios)
            and not self.prohibited_artifact_paths
        )
        if self.passed != expected:
            raise ValueError("supervised rehearsal passed status must match")
        if len({item.scenario for item in self.scenarios}) != len(
            self.scenarios
        ):
            raise ValueError("supervised rehearsal scenarios must be unique")
        return self


class AutonomousDryRunRehearsalScenarioResult(FrozenModel):
    """Evidence summary for one autonomous dry-run rehearsal scenario."""

    scenario: AutonomousDryRunRehearsalScenario
    passed: bool
    authorization_path: str = Field(min_length=1)
    run_ids: tuple[str, ...] = Field(min_length=1)
    run_statuses: tuple[AutonomousDryRunStatus, ...] = Field(min_length=1)
    run_paths: tuple[str, ...] = Field(min_length=1)
    workflow_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_sequences_must_align(
        self,
    ) -> "AutonomousDryRunRehearsalScenarioResult":
        if not (
            len(self.run_ids) == len(self.run_statuses) == len(self.run_paths)
        ):
            raise ValueError("autonomous rehearsal run evidence must align")
        return self


class AutonomousDryRunRehearsalReport(FrozenModel):
    """Immutable report for bounded autonomous dry-run rehearsal evidence."""

    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evaluated_at: AwareDatetime
    passed: bool
    scenarios: tuple[AutonomousDryRunRehearsalScenarioResult, ...] = Field(
        min_length=1
    )
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_scenarios(
        self,
    ) -> "AutonomousDryRunRehearsalReport":
        if self.passed != all(item.passed for item in self.scenarios):
            raise ValueError("autonomous rehearsal passed status must match")
        if len({item.scenario for item in self.scenarios}) != len(
            self.scenarios
        ):
            raise ValueError("autonomous rehearsal scenarios must be unique")
        return self
