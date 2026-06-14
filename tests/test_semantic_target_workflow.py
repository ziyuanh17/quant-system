from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    SemanticPaperBrokerState,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    ResearchRiskPolicy,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.models.workflow import SemanticTargetWorkflowStatus
from quant.workflows import (
    run_semantic_target_dry_run_workflow,
    run_semantic_target_paper_workflow,
)


def test_dry_run_workflow_persists_complete_pipeline_and_is_restart_safe(
    tmp_path,
) -> None:
    first = _run_dry(tmp_path)
    second = _run_dry(tmp_path)

    assert first == second
    assert first.record.status == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
    assert first.record.dry_run_status == ExecutionDryRunStatus.WOULD_SUBMIT
    assert len(tuple((tmp_path / "strategy-targets").rglob("*.json"))) == 1
    assert len(tuple((tmp_path / "strategy-evaluations").rglob("*.json"))) == 1
    assert len(tuple((tmp_path / "portfolio-targets").rglob("*.json"))) == 1
    assert len(tuple((tmp_path / "risk-targets").rglob("*.json"))) == 1
    assert len(tuple((tmp_path / "lifecycle" / "plans").glob("*.json"))) == 1
    assert len(tuple((tmp_path / "orchestrations").glob("*.json"))) == 1


def test_workflow_persists_unavailable_contributor_block_without_plan(
    tmp_path,
) -> None:
    decision = _decision(
        target_value=None,
        declared_status=TargetDeclaredStatus.UNAVAILABLE,
    )
    evaluation = _evaluation(
        outcome=StrategyEvaluationOutcome.UNAVAILABLE,
        effective_target_decision_id=None,
    )

    result = _run_dry(
        tmp_path,
        decisions=(decision,),
        evaluations=(evaluation,),
    )

    assert (
        result.record.status == SemanticTargetWorkflowStatus.PORTFOLIO_BLOCKED
    )
    assert result.record.execution_plan_id is None
    assert not (tmp_path / "lifecycle" / "plans").exists()


def test_workflow_persists_risk_rejection_without_plan(tmp_path) -> None:
    result = _run_dry(
        tmp_path,
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("1"),
        ),
    )

    assert result.record.status == SemanticTargetWorkflowStatus.RISK_REJECTED
    assert result.record.execution_plan_id is None
    assert not (tmp_path / "lifecycle" / "plans").exists()


def test_workflow_persists_fractional_operational_block_without_rounding(
    tmp_path,
) -> None:
    decision = _decision(target_value=Decimal("1.5"))

    result = _run_dry(
        tmp_path,
        decisions=(decision,),
        evaluations=(_evaluation(decision_id=decision.decision_id),),
    )

    assert (
        result.record.status
        == SemanticTargetWorkflowStatus.OPERATIONALLY_BLOCKED
    )
    assert "cannot be fractional" in result.record.reason
    assert result.risk_target.approved_target_value == Decimal("1.5")
    assert not (tmp_path / "lifecycle" / "plans").exists()


def test_workflow_persists_stale_target_as_portfolio_block(tmp_path) -> None:
    decision = _decision().model_copy(
        update={"valid_until": _now() + timedelta(hours=3)}
    )

    result = _run_dry(
        tmp_path,
        decisions=(decision,),
        evaluated_at=_now() + timedelta(hours=2),
    )

    assert (
        result.record.status == SemanticTargetWorkflowStatus.PORTFOLIO_BLOCKED
    )
    assert not (tmp_path / "lifecycle" / "plans").exists()


def test_workflow_records_working_order_as_blocked_dry_run(tmp_path) -> None:
    result = _run_dry(
        tmp_path,
        account=_account(open_order_ids=("working-order-1",)),
    )

    assert result.record.status == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
    assert result.record.dry_run_status == ExecutionDryRunStatus.BLOCKED
    assert result.record.execution_plan_id is not None


def test_local_paper_workflow_reaches_satisfaction_and_does_not_duplicate(
    tmp_path,
) -> None:
    first = _run_paper(tmp_path)
    second = _run_paper(tmp_path)

    assert first == second
    assert (
        first.record.status
        == SemanticTargetWorkflowStatus.EXECUTION_COMPLETED
    )
    assert first.record.execution_status == ExecutionPlanStatus.SATISFIED
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "semantic-paper" / "state.json").read_text()
    )
    assert state.positions[0].quantity == 2
    assert len(state.orders) == 1
    assert len(state.fills) == 1


def test_local_paper_workflow_requires_reconciliation_runner_identity(
    tmp_path,
) -> None:
    with pytest.raises(ValueError, match="must not be empty"):
        run_semantic_target_paper_workflow(
            orchestration_id="orchestration-paper-1",
            contributor_set=_contributor_set(),
            strategy_decisions=(_decision(),),
            strategy_evaluations=(_evaluation(),),
            risk_policy=_risk_policy(),
            portfolio_target_id="portfolio-paper-1",
            portfolio_target_revision=1,
            risk_target_id="risk-paper-1",
            risk_target_revision=1,
            policy=_execution_policy(),
            reference_price=100,
            safety_check=TradingSafetyCheck(
                mode=TradingMode.PAPER,
                allowed=True,
            ),
            output_root=tmp_path,
            initial_cash=1_000,
            evaluated_at=_now(),
            reconciliation_runner_id="",
        )


def test_orchestration_identity_cannot_be_reused_for_other_decisions(
    tmp_path,
) -> None:
    _run_dry(tmp_path)
    changed = _decision(decision_id="decision-other")

    with pytest.raises(ValueError, match="already bound"):
        _run_dry(
            tmp_path,
            decisions=(changed,),
            evaluations=(
                _evaluation(
                    decision_id=changed.decision_id,
                    effective_target_decision_id=changed.decision_id,
                ),
            ),
        )


def test_workflow_requires_one_evaluation_per_contributor(tmp_path) -> None:
    with pytest.raises(ValueError, match="requires one evaluation"):
        _run_dry(tmp_path, evaluations=())

    assert not (tmp_path / "strategy-targets").exists()


def _run_dry(
    root,
    *,
    decisions: tuple[StrategyTargetDecision, ...] | None = None,
    evaluations: tuple[StrategyEvaluation, ...] | None = None,
    risk_policy: ResearchRiskPolicy | None = None,
    account: LiveAccountSnapshot | None = None,
    evaluated_at: datetime | None = None,
):
    decision = _decision()
    return run_semantic_target_dry_run_workflow(
        orchestration_id="orchestration-1",
        contributor_set=_contributor_set(),
        strategy_decisions=(decision,) if decisions is None else decisions,
        strategy_evaluations=(
            (_evaluation(),) if evaluations is None else evaluations
        ),
        risk_policy=risk_policy or _risk_policy(),
        portfolio_target_id="portfolio-1",
        portfolio_target_revision=1,
        risk_target_id="risk-1",
        risk_target_revision=1,
        account=account or _account(),
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        output_root=root,
        evaluated_at=evaluated_at or _now(),
    )


def _run_paper(root):
    return run_semantic_target_paper_workflow(
        orchestration_id="orchestration-paper-1",
        contributor_set=_contributor_set(),
        strategy_decisions=(_decision(),),
        strategy_evaluations=(_evaluation(),),
        risk_policy=_risk_policy(),
        portfolio_target_id="portfolio-paper-1",
        portfolio_target_revision=1,
        risk_target_id="risk-paper-1",
        risk_target_revision=1,
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.PAPER,
            allowed=True,
        ),
        output_root=root,
        initial_cash=1_000,
        evaluated_at=_now(),
    )


def _decision(
    *,
    decision_id: str = "decision-1",
    target_value: Decimal | None = Decimal("2"),
    declared_status: TargetDeclaredStatus = TargetDeclaredStatus.ACTIVE,
) -> StrategyTargetDecision:
    return StrategyTargetDecision(
        decision_id=decision_id,
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target_value,
        sizing_policy_version="fixed_shares_v1",
        input_data_id="bars-sha256",
        generated_at=_now(),
        effective_at=_now(),
        valid_until=_now() + timedelta(hours=1),
        declared_status=declared_status,
        reason="controlled target",
    )


def _evaluation(
    *,
    decision_id: str = "decision-1",
    outcome: StrategyEvaluationOutcome = StrategyEvaluationOutcome.NEW_TARGET,
    effective_target_decision_id: str | None = "decision-1",
) -> StrategyEvaluation:
    return StrategyEvaluation(
        evaluation_id=f"evaluation-{decision_id}",
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        evaluated_at=_now(),
        outcome=outcome,
        effective_target_decision_id=effective_target_decision_id,
        reason="controlled evaluation",
    )


def _contributor_set() -> ContributorSet:
    return ContributorSet(
        contributor_set_id="aapl-v1",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled ownership",
    )


def _risk_policy() -> ResearchRiskPolicy:
    return ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("10"),
    )


def _execution_policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _account(
    *, open_order_ids: tuple[str, ...] = ()
) -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        id="dry-account-1",
        broker_name="local-dry-run",
        account_id="local-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        open_order_ids=open_order_ids,
        captured_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 6, 13, 12, tzinfo=UTC)
