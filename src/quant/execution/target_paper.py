from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from quant.execution.artifacts import write_live_reconciliation_report
from quant.execution.lifecycle_artifacts import (
    current_execution_status,
    execution_plan_path,
    load_execution_plan,
)
from quant.execution.reconciliation import reconcile_live_state
from quant.execution.semantic_paper import (
    SemanticPaperBrokerAdapter,
    SemanticPaperBrokerClient,
)
from quant.execution.target_lifecycle import (
    claim_execution_plan,
    confirm_execution_satisfaction,
    recover_execution_submission,
    refresh_submitted_execution,
    submit_execution_plan,
)
from quant.models.execution import (
    LiveReconciliationReport,
    Position,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionLifecyclePolicy,
    ExecutionPlan,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    PortfolioTargetDecision,
    ResearchRiskPolicy,
    RiskTargetDecision,
    StrategyTargetDecision,
)
from quant.operations import FileLock


@dataclass(frozen=True)
class SemanticPaperRunResult:
    plan: ExecutionPlan
    status: ExecutionPlanStatus
    reconciliation: LiveReconciliationReport | None


def run_semantic_target_paper(
    *,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    state_path: Path,
    artifact_root: Path,
    order_output_dir: Path,
    fill_output_dir: Path,
    snapshot_output_dir: Path,
    reconciliation_output_dir: Path,
    initial_cash: float,
    evaluated_at: datetime,
    initial_positions: tuple[Position, ...] = (),
    evidence_refs: tuple[str, ...] = (),
) -> SemanticPaperRunResult:
    """Run one semantic target through the durable local paper lifecycle."""
    client = SemanticPaperBrokerClient(
        state_path=state_path,
        initial_cash=initial_cash,
        initial_positions=initial_positions,
    )
    adapter = SemanticPaperBrokerAdapter(
        client=client,
        order_output_dir=order_output_dir,
        fill_output_dir=fill_output_dir,
        snapshot_output_dir=snapshot_output_dir,
    )
    account = adapter.account_snapshot()
    try:
        plan = claim_execution_plan(
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            account=account,
            policy=policy,
            artifact_root=artifact_root,
            created_at=evaluated_at,
            evidence_refs=evidence_refs,
        )
    except FileExistsError:
        plan = load_execution_plan(
            execution_plan_path(
                artifact_root,
                risk_target.risk_target_id,
                risk_target.revision,
            )
        )

    with FileLock(
        path=artifact_root
        / "locks"
        / f"{plan.execution_plan_id}-semantic-paper.lock",
        lock_name=f"semantic-paper-run:{plan.execution_plan_id}",
        stale_after_seconds=300,
    ):
        status = _advance_execution(
            plan=plan,
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            risk_policy=risk_policy,
            adapter=adapter,
            reference_price=reference_price,
            safety_check=safety_check,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
        )
        if status in {
            ExecutionPlanStatus.BLOCKED,
            ExecutionPlanStatus.REJECTED,
            ExecutionPlanStatus.CANCELLED,
        }:
            return SemanticPaperRunResult(plan, status, None)
        if status == ExecutionPlanStatus.SATISFIED:
            return SemanticPaperRunResult(plan, status, None)
        if status not in {
            ExecutionPlanStatus.FILLED,
            ExecutionPlanStatus.PLANNED,
        }:
            return SemanticPaperRunResult(plan, status, None)

        _materialize_order_evidence(plan=plan, adapter=adapter)
        adapter.account_snapshot()
        reconciliation = reconcile_live_state(
            client=client,
            order_records_dir=order_output_dir,
            fill_records_dir=fill_output_dir,
            snapshot_records_dir=snapshot_output_dir,
        )
        write_live_reconciliation_report(
            reconciliation,
            reconciliation_output_dir
            / plan.execution_plan_id
            / f"{reconciliation.id}.json",
        )
        status = confirm_execution_satisfaction(
            plan=plan,
            broker=adapter,
            reconciliation=reconciliation,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
        )
        return SemanticPaperRunResult(plan, status, reconciliation)


def _advance_execution(
    *,
    plan: ExecutionPlan,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    adapter: SemanticPaperBrokerAdapter,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    artifact_root: Path,
    evaluated_at: datetime,
) -> ExecutionPlanStatus:
    status = current_execution_status(plan, artifact_root)
    if status == ExecutionPlanStatus.PLANNED:
        return submit_execution_plan(
            plan=plan,
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            risk_policy=risk_policy,
            broker=adapter,
            reference_price=reference_price,
            safety_check=safety_check,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
            expected_trading_mode=TradingMode.PAPER,
        )
    if status in {
        ExecutionPlanStatus.SUBMISSION_PENDING,
        ExecutionPlanStatus.AMBIGUOUS,
    }:
        recover_execution_submission(
            plan=plan,
            broker=adapter,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
        )
        return current_execution_status(plan, artifact_root)
    if status == ExecutionPlanStatus.SUBMITTED:
        refresh_submitted_execution(
            plan=plan,
            broker=adapter,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
        )
        return current_execution_status(plan, artifact_root)
    return status


def _materialize_order_evidence(
    *,
    plan: ExecutionPlan,
    adapter: SemanticPaperBrokerAdapter,
) -> None:
    if plan.order_request is None:
        return
    orders = adapter.orders_by_client_order_id(plan.client_order_id)
    if len(orders) != 1:
        raise ValueError(
            "semantic paper reconciliation requires one planned order"
        )
    adapter.refresh_order_record(orders[0])
