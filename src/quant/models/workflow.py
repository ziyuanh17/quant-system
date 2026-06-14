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
