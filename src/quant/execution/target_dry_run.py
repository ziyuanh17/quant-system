"""Observe semantic-target execution plans without submission."""

from datetime import datetime
from pathlib import Path

from quant.execution.lifecycle_artifacts import (
    current_execution_status,
    execution_dry_run_observation_path,
    execution_plan_path,
    load_execution_dry_run_observation,
    load_execution_plan,
    write_execution_dry_run_observation,
)
from quant.execution.target_lifecycle import (
    claim_execution_plan,
    validate_pre_submission,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunObservation,
    ExecutionDryRunStatus,
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


class _SnapshotStateReader:
    def __init__(self, account: LiveAccountSnapshot) -> None:
        self._account = account

    def account_snapshot(self) -> LiveAccountSnapshot:
        return self._account

    def has_open_orders(self) -> bool:
        return bool(self._account.open_order_ids)


def run_semantic_target_dry_run(
    *,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    account: LiveAccountSnapshot,
    policy: ExecutionLifecyclePolicy,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    artifact_root: Path,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> ExecutionDryRunObservation:
    """Claim or recover a plan, then persist its single dry-run observation."""
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

    observation_path = execution_dry_run_observation_path(
        artifact_root,
        plan.execution_plan_id,
        f"dry-run-{plan.execution_plan_id}",
    )
    lock_path = (
        artifact_root / "locks" / f"{plan.execution_plan_id}-dry-run.lock"
    )
    with FileLock(
        path=lock_path,
        lock_name=f"execution-dry-run:{plan.execution_plan_id}",
        stale_after_seconds=300,
    ):
        if observation_path.exists():
            return load_execution_dry_run_observation(observation_path)
        return observe_execution_plan_dry_run(
            plan=plan,
            risk_target=risk_target,
            portfolio_target=portfolio_target,
            contributor_set=contributor_set,
            strategy_decisions=strategy_decisions,
            risk_policy=risk_policy,
            account=account,
            reference_price=reference_price,
            safety_check=safety_check,
            artifact_root=artifact_root,
            evaluated_at=evaluated_at,
            evidence_refs=evidence_refs,
        )


def observe_execution_plan_dry_run(
    *,
    plan: ExecutionPlan,
    risk_target: RiskTargetDecision,
    portfolio_target: PortfolioTargetDecision,
    contributor_set: ContributorSet,
    strategy_decisions: tuple[StrategyTargetDecision, ...],
    risk_policy: ResearchRiskPolicy,
    account: LiveAccountSnapshot,
    reference_price: float,
    safety_check: TradingSafetyCheck,
    artifact_root: Path,
    evaluated_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> ExecutionDryRunObservation:
    """Persist what a valid plan would do without changing lifecycle state."""
    if (
        current_execution_status(plan, artifact_root)
        != ExecutionPlanStatus.PLANNED
    ):
        raise ValueError("only a planned execution may be dry-run evaluated")

    reasons = validate_pre_submission(
        plan=plan,
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=strategy_decisions,
        risk_policy=risk_policy,
        broker=_SnapshotStateReader(account),
        reference_price=reference_price,
        safety_check=safety_check,
        evaluated_at=evaluated_at,
        expected_trading_mode=TradingMode.DRY_RUN,
    )
    if reasons:
        status = ExecutionDryRunStatus.BLOCKED
        reason = "dry-run revalidation blocked"
    elif plan.order_request is None:
        status = ExecutionDryRunStatus.ALREADY_SATISFIED
        reason = "approved target already matches the observed position"
    else:
        status = ExecutionDryRunStatus.WOULD_SUBMIT
        reason = "eligible order recorded without broker submission"

    observation = ExecutionDryRunObservation(
        observation_id=f"dry-run-{plan.execution_plan_id}",
        execution_plan_id=plan.execution_plan_id,
        risk_target_id=plan.risk_target_id,
        risk_target_revision=plan.risk_target_revision,
        account_snapshot_id=account.id,
        broker_name=account.broker_name,
        account_id=account.account_id,
        broker_environment=account.broker_environment,
        symbol=plan.symbol,
        current_quantity=next(
            (
                position.quantity
                for position in account.positions
                if position.symbol == plan.symbol
            ),
            0,
        ),
        target_quantity=plan.target_quantity,
        order_request=plan.order_request,
        reference_price=reference_price,
        notional=(
            plan.order_request.quantity * reference_price
            if plan.order_request is not None and reference_price > 0
            else 0
        ),
        safety_check=safety_check,
        status=status,
        validation_reasons=reasons,
        observed_at=evaluated_at,
        reason=reason,
        evidence_refs=evidence_refs,
    )
    write_execution_dry_run_observation(observation, artifact_root)
    return observation
