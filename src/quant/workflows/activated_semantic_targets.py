import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from pydantic import BaseModel

from quant.execution.reconciliation import reconcile_live_state
from quant.execution.target_paper import SemanticPaperReconciliationRunner
from quant.models.activation import (
    ActivationDecision,
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationConsumption,
    SemanticTargetActivationEvaluation,
    SemanticTargetActivationScope,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    Position,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.targets import (
    ContributorSet,
    ResearchRiskPolicy,
    StrategyEvaluation,
    StrategyTargetDecision,
)
from quant.operations import FileLock
from quant.workflows.semantic_target_activation import (
    evaluate_semantic_target_activation,
)
from quant.workflows.semantic_targets import (
    SemanticTargetWorkflowResult,
    run_semantic_target_dry_run_workflow,
    run_semantic_target_paper_workflow,
)


@dataclass(frozen=True)
class ActivatedSemanticTargetWorkflowResult:
    activation_evaluation: SemanticTargetActivationEvaluation
    activation_consumption: SemanticTargetActivationConsumption
    workflow: SemanticTargetWorkflowResult | None


def run_activated_semantic_target_dry_run_workflow(
    *,
    activation_evaluation_id: str,
    authorization: SemanticTargetActivationAuthorization,
    rehearsal_report_path: Path,
    activation_root: Path,
    orchestration_id: str,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    account: LiveAccountSnapshot,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    output_root: Path,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> ActivatedSemanticTargetWorkflowResult:
    """Run dry-run orchestration only after durable activation consumption."""

    def run(activation_ref: str) -> SemanticTargetWorkflowResult:
        return run_semantic_target_dry_run_workflow(
            orchestration_id=orchestration_id,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            strategy_evaluations=strategy_evaluations,
            risk_policy=risk_policy,
            portfolio_target_id=portfolio_target_id,
            portfolio_target_revision=portfolio_target_revision,
            risk_target_id=risk_target_id,
            risk_target_revision=risk_target_revision,
            account=account,
            policy=policy,
            reference_price=reference_price,
            safety_check=safety_check,
            output_root=output_root,
            evaluated_at=evaluated_at,
            evidence_refs=(*evidence_refs, activation_ref),
        )

    return _run_activated(
        activation_evaluation_id=activation_evaluation_id,
        authorization=authorization,
        rehearsal_report_path=rehearsal_report_path,
        activation_root=activation_root,
        requested_scope=SemanticTargetActivationScope.DRY_RUN,
        orchestration_id=orchestration_id,
        evaluated_at=evaluated_at,
        run=run,
    )


def run_activated_semantic_target_paper_workflow(
    *,
    activation_evaluation_id: str,
    authorization: SemanticTargetActivationAuthorization,
    rehearsal_report_path: Path,
    activation_root: Path,
    orchestration_id: str,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    strategy_evaluations: tuple[StrategyEvaluation, ...],
    risk_policy: ResearchRiskPolicy,
    portfolio_target_id: str,
    portfolio_target_revision: int,
    risk_target_id: str,
    risk_target_revision: int,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    output_root: Path,
    initial_cash: float,
    evaluated_at: datetime,
    initial_positions: tuple[Position, ...] = (),
    evidence_refs: tuple[str, ...] = (),
    reconciliation_runner: SemanticPaperReconciliationRunner = (
        reconcile_live_state
    ),
    reconciliation_runner_id: str = "reconcile_live_state_v1",
) -> ActivatedSemanticTargetWorkflowResult:
    """Run local semantic paper only after durable activation consumption."""

    def run(activation_ref: str) -> SemanticTargetWorkflowResult:
        return run_semantic_target_paper_workflow(
            orchestration_id=orchestration_id,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            strategy_evaluations=strategy_evaluations,
            risk_policy=risk_policy,
            portfolio_target_id=portfolio_target_id,
            portfolio_target_revision=portfolio_target_revision,
            risk_target_id=risk_target_id,
            risk_target_revision=risk_target_revision,
            policy=policy,
            reference_price=reference_price,
            safety_check=safety_check,
            output_root=output_root,
            initial_cash=initial_cash,
            evaluated_at=evaluated_at,
            initial_positions=initial_positions,
            evidence_refs=(*evidence_refs, activation_ref),
            reconciliation_runner=reconciliation_runner,
            reconciliation_runner_id=reconciliation_runner_id,
        )

    return _run_activated(
        activation_evaluation_id=activation_evaluation_id,
        authorization=authorization,
        rehearsal_report_path=rehearsal_report_path,
        activation_root=activation_root,
        requested_scope=SemanticTargetActivationScope.SEMANTIC_PAPER,
        orchestration_id=orchestration_id,
        evaluated_at=evaluated_at,
        run=run,
    )


def load_semantic_target_activation_consumption(
    path: Path,
) -> SemanticTargetActivationConsumption:
    return SemanticTargetActivationConsumption.model_validate_json(
        path.read_text()
    )


def _run_activated(
    *,
    activation_evaluation_id: str,
    authorization: SemanticTargetActivationAuthorization,
    rehearsal_report_path: Path,
    activation_root: Path,
    requested_scope: SemanticTargetActivationScope,
    orchestration_id: str,
    evaluated_at: datetime,
    run: Callable[[str], SemanticTargetWorkflowResult],
) -> ActivatedSemanticTargetWorkflowResult:
    _require_safe_component(orchestration_id)
    evaluation = evaluate_semantic_target_activation(
        evaluation_id=activation_evaluation_id,
        authorization=authorization,
        requested_scope=requested_scope,
        rehearsal_report_path=rehearsal_report_path,
        output_root=activation_root,
        evaluated_at=evaluated_at,
    )
    evaluation_path = (
        activation_root / "evaluations" / f"{activation_evaluation_id}.json"
    )
    consumption = SemanticTargetActivationConsumption(
        consumption_id=f"{activation_evaluation_id}:{orchestration_id}",
        orchestration_id=orchestration_id,
        requested_scope=requested_scope,
        activation_evaluation_id=activation_evaluation_id,
        activation_decision=evaluation.decision,
        consumed_at=evaluated_at,
        activation_evaluation_path=str(evaluation_path),
        reason=(
            "activation evaluation allowed orchestration"
            if evaluation.decision == ActivationDecision.ALLOWED
            else "; ".join(evaluation.issues)
        ),
    )
    consumption_path = _persist_or_verify_consumption(
        consumption, activation_root
    )
    if evaluation.decision == ActivationDecision.BLOCKED:
        return ActivatedSemanticTargetWorkflowResult(
            activation_evaluation=evaluation,
            activation_consumption=consumption,
            workflow=None,
        )
    workflow = run(str(consumption_path))
    return ActivatedSemanticTargetWorkflowResult(
        activation_evaluation=evaluation,
        activation_consumption=consumption,
        workflow=workflow,
    )


def _persist_or_verify_consumption(
    consumption: SemanticTargetActivationConsumption,
    output_root: Path,
) -> Path:
    _require_safe_component(consumption.activation_evaluation_id)
    _require_safe_component(consumption.orchestration_id)
    path = (
        output_root
        / "consumptions"
        / f"{consumption.activation_evaluation_id}.json"
    )
    with FileLock(
        path=(
            output_root
            / "locks"
            / f"{consumption.activation_evaluation_id}-consumption.lock"
        ),
        lock_name=(
            "semantic-target-activation-consumption:"
            f"{consumption.activation_evaluation_id}"
        ),
        stale_after_seconds=300,
    ):
        if path.exists():
            if load_semantic_target_activation_consumption(path) != consumption:
                raise ValueError(
                    "immutable activation consumption conflicts with input"
                )
            return path
        _write_model_exclusive(path, consumption)
        return path


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_safe_component(value: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("activation consumption IDs must be safe components")
