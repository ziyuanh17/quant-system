"""Define domain models for durable workflow and rehearsal records."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import uuid4

from pydantic import Field, model_validator

from quant.models.base import FrozenModel
from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionPlanStatus,
)


class WorkflowRunStatus(StrEnum):
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class SemanticTargetWorkflowMode(StrEnum):
    DRY_RUN = "dry_run"
    SEMANTIC_PAPER = "semantic_paper"


class SemanticTargetWorkflowStatus(StrEnum):
    PORTFOLIO_BLOCKED = "portfolio_blocked"
    RISK_REJECTED = "risk_rejected"
    OPERATIONALLY_BLOCKED = "operationally_blocked"
    DRY_RUN_OBSERVED = "dry_run_observed"
    EXECUTION_COMPLETED = "execution_completed"


class SemanticTargetRehearsalScenario(StrEnum):
    DRY_RUN_ELIGIBLE = "dry_run_eligible"
    DRY_RUN_RESTART = "dry_run_restart"
    STALE_TARGET_BLOCK = "stale_target_block"
    WORKING_ORDER_BLOCK = "working_order_block"
    RISK_REJECTION = "risk_rejection"
    FRACTIONAL_TARGET_BLOCK = "fractional_target_block"
    LOCAL_PAPER_RESTART = "local_paper_restart"
    RECONCILIATION_FAILURE = "reconciliation_failure"


class SemanticTargetWorkflowRecord(FrozenModel):
    """Immutable result linking one controlled semantic-target run."""

    schema_version: Literal[1] = 1
    orchestration_id: str = Field(min_length=1)
    input_fingerprint: str = Field(min_length=1)
    mode: SemanticTargetWorkflowMode
    status: SemanticTargetWorkflowStatus
    evaluated_at: datetime
    contributor_set_id: str = Field(min_length=1)
    contributor_set_revision: int = Field(ge=1)
    strategy_decision_ids: tuple[str, ...] = ()
    strategy_evaluation_ids: tuple[str, ...] = ()
    portfolio_target_id: str = Field(min_length=1)
    portfolio_target_revision: int = Field(ge=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    artifact_paths: tuple[str, ...] = Field(min_length=1)
    execution_plan_id: str | None = None
    execution_status: ExecutionPlanStatus | None = None
    dry_run_observation_id: str | None = None
    dry_run_status: ExecutionDryRunStatus | None = None
    reconciliation_report_id: str | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_outcome_evidence(self) -> "SemanticTargetWorkflowRecord":
        if self.status == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED:
            if (
                self.execution_plan_id is None
                or self.dry_run_observation_id is None
                or self.dry_run_status is None
                or self.execution_status is not None
            ):
                raise ValueError(
                    "dry-run workflows require plan and observation evidence"
                )
        elif self.status == SemanticTargetWorkflowStatus.EXECUTION_COMPLETED:
            if (
                self.execution_plan_id is None
                or self.execution_status is None
                or self.dry_run_observation_id is not None
                or self.dry_run_status is not None
            ):
                raise ValueError(
                    "completed execution workflows require execution evidence"
                )
        elif any(
            item is not None
            for item in (
                self.execution_plan_id,
                self.execution_status,
                self.dry_run_observation_id,
                self.dry_run_status,
                self.reconciliation_report_id,
            )
        ):
            raise ValueError(
                "blocked or rejected workflows must not claim execution"
            )
        return self


class SemanticTargetRehearsalScenarioResult(FrozenModel):
    scenario: SemanticTargetRehearsalScenario
    passed: bool
    orchestration_ids: tuple[str, ...] = Field(min_length=1)
    workflow_statuses: tuple[SemanticTargetWorkflowStatus, ...] = Field(
        min_length=1
    )
    execution_statuses: tuple[ExecutionPlanStatus | None, ...] = Field(
        min_length=1
    )
    dry_run_statuses: tuple[ExecutionDryRunStatus | None, ...] = Field(
        min_length=1
    )
    evidence_paths: tuple[str, ...] = Field(min_length=1)
    supporting_evidence_paths: tuple[str, ...] = ()
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def evidence_sequences_must_align(
        self,
    ) -> "SemanticTargetRehearsalScenarioResult":
        count = len(self.orchestration_ids)
        if (
            len(self.workflow_statuses) != count
            or len(self.execution_statuses) != count
            or len(self.dry_run_statuses) != count
        ):
            raise ValueError("rehearsal scenario outcome sequences must align")
        return self


class SemanticTargetRehearsalReport(FrozenModel):
    schema_version: Literal[1] = 1
    rehearsal_id: str = Field(min_length=1)
    rehearsal_policy_version: str = Field(min_length=1)
    evaluated_at: datetime
    passed: bool
    scenarios: tuple[SemanticTargetRehearsalScenarioResult, ...] = Field(
        min_length=1
    )
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def passed_must_match_scenarios(self) -> "SemanticTargetRehearsalReport":
        if self.passed != all(item.passed for item in self.scenarios):
            raise ValueError("rehearsal passed status must match scenarios")
        if len({item.scenario for item in self.scenarios}) != len(
            self.scenarios
        ):
            raise ValueError("rehearsal scenarios must be unique")
        return self


class DataRefreshWorkflowRecord(FrozenModel):
    """Audit record for one refresh-then-paper-signal workflow attempt."""

    workflow_id: str = Field(default_factory=lambda: str(uuid4()))
    workflow_name: str = "paper-signal-refresh"
    status: WorkflowRunStatus
    started_at: datetime
    completed_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    provider: str
    symbol: str
    request_start: str
    request_end: str | None = None
    message: str
    raw_path: str | None = None
    normalized_path: str | None = None
    validation_report_path: str | None = None
    metadata_path: str | None = None
    lock_path: str | None = None
    lock_owner: str | None = None
    scheduler_run_paths: tuple[str, ...] = ()
    artifact_paths: tuple[str, ...] = ()
    latest_signal_action: str | None = None
    latest_signal_reason: str | None = None
    latest_signal_market_price: float | None = None
    broker_submission_attempted: bool | None = None
    broker_submission_skipped_reason: str | None = None
    broker_position_quantity_before: int | None = None
    strategy_target_quantity: int | None = None
    planned_order_side: str | None = None
    planned_order_quantity: int | None = None
    order_artifact_paths: tuple[str, ...] = ()
    fill_artifact_paths: tuple[str, ...] = ()
    snapshot_artifact_paths: tuple[str, ...] = ()
    reconciliation_report_path: str | None = None

    @property
    def duration_seconds(self) -> float:
        return (self.completed_at - self.started_at).total_seconds()
