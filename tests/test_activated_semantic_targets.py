from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.activation import (
    ActivationDecision,
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationScope,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
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
    SEMANTIC_TARGET_ORCHESTRATION_POLICY,
    SEMANTIC_TARGET_REHEARSAL_POLICY,
    rehearsal_report_sha256,
    run_activated_semantic_target_dry_run_workflow,
    run_activated_semantic_target_paper_workflow,
    run_semantic_target_local_rehearsal,
)


def test_activated_dry_run_binds_consumption_and_is_restart_safe(
    tmp_path,
) -> None:
    report_path, authorization = _authorization(tmp_path)

    first = _run_dry(tmp_path, report_path, authorization)
    second = _run_dry(tmp_path, report_path, authorization)

    assert first == second
    assert first.activation_evaluation.decision == ActivationDecision.ALLOWED
    assert first.workflow is not None
    assert (
        first.workflow.record.status
        == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
    )
    consumption_path = (
        tmp_path
        / "activation"
        / "consumptions"
        / "activation-dry-1.json"
    )
    assert consumption_path.is_file()
    assert (
        str(consumption_path)
        in first.workflow.portfolio_target.evidence_refs
    )
    assert str(consumption_path) in first.workflow.risk_target.evidence_refs


def test_activated_local_paper_executes_once_across_restart(tmp_path) -> None:
    report_path, authorization = _authorization(tmp_path)

    first = _run_paper(tmp_path, report_path, authorization)
    second = _run_paper(tmp_path, report_path, authorization)

    assert first == second
    assert first.workflow is not None
    assert (
        first.workflow.record.execution_status
        == ExecutionPlanStatus.SATISFIED
    )
    paper_root = tmp_path / "paper" / "semantic-paper"
    assert len(tuple((paper_root / "orders").glob("*.json"))) == 1
    assert len(tuple((paper_root / "fills").glob("*.json"))) == 1


def test_blocked_activation_creates_no_target_or_execution_artifacts(
    tmp_path,
) -> None:
    report_path, authorization = _authorization(
        tmp_path,
        valid_until=_now(),
    )

    result = _run_dry(tmp_path, report_path, authorization)

    assert result.activation_evaluation.decision == ActivationDecision.BLOCKED
    assert result.workflow is None
    assert "authorization is expired" in result.activation_consumption.reason
    assert not (tmp_path / "dry").exists()
    assert (
        tmp_path
        / "activation"
        / "consumptions"
        / "activation-dry-1.json"
    ).is_file()


def test_scope_mismatch_blocks_local_paper_before_artifacts(tmp_path) -> None:
    report_path, authorization = _authorization(
        tmp_path,
        scopes=(SemanticTargetActivationScope.DRY_RUN,),
    )

    result = _run_paper(tmp_path, report_path, authorization)

    assert result.activation_evaluation.decision == ActivationDecision.BLOCKED
    assert result.workflow is None
    assert not (tmp_path / "paper").exists()


def test_tampered_rehearsal_blocks_before_orchestration(tmp_path) -> None:
    report_path, authorization = _authorization(tmp_path)
    report_path.write_text(
        report_path.read_text().replace("all controlled", "changed")
    )

    result = _run_dry(tmp_path, report_path, authorization)

    assert result.activation_evaluation.decision == ActivationDecision.BLOCKED
    assert result.workflow is None
    assert not (tmp_path / "dry").exists()


def test_activation_evaluation_can_be_consumed_by_only_one_orchestration(
    tmp_path,
) -> None:
    report_path, authorization = _authorization(tmp_path)
    _run_dry(tmp_path, report_path, authorization)

    try:
        run_activated_semantic_target_dry_run_workflow(
            activation_evaluation_id="activation-dry-1",
            authorization=authorization,
            rehearsal_report_path=report_path,
            activation_root=tmp_path / "activation",
            orchestration_id="another-orchestration",
            contributor_set=_contributor_set(),
            strategy_decisions=(_decision(),),
            strategy_evaluations=(_evaluation(),),
            risk_policy=_risk_policy(),
            portfolio_target_id="portfolio-other",
            portfolio_target_revision=1,
            risk_target_id="risk-other",
            risk_target_revision=1,
            account=_account(),
            policy=_execution_policy(),
            reference_price=100,
            safety_check=TradingSafetyCheck(
                mode=TradingMode.DRY_RUN,
                allowed=True,
            ),
            output_root=tmp_path / "other",
            evaluated_at=_now(),
        )
    except ValueError as error:
        assert "consumption conflicts" in str(error)
    else:
        raise AssertionError("activation evaluation was consumed twice")

    assert not (tmp_path / "other").exists()


def _run_dry(root, report_path, authorization):
    return run_activated_semantic_target_dry_run_workflow(
        activation_evaluation_id="activation-dry-1",
        authorization=authorization,
        rehearsal_report_path=report_path,
        activation_root=root / "activation",
        orchestration_id="activated-dry-1",
        contributor_set=_contributor_set(),
        strategy_decisions=(_decision(),),
        strategy_evaluations=(_evaluation(),),
        risk_policy=_risk_policy(),
        portfolio_target_id="portfolio-dry-1",
        portfolio_target_revision=1,
        risk_target_id="risk-dry-1",
        risk_target_revision=1,
        account=_account(),
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        output_root=root / "dry",
        evaluated_at=_now(),
    )


def _run_paper(root, report_path, authorization):
    return run_activated_semantic_target_paper_workflow(
        activation_evaluation_id="activation-paper-1",
        authorization=authorization,
        rehearsal_report_path=report_path,
        activation_root=root / "activation",
        orchestration_id="activated-paper-1",
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
        output_root=root / "paper",
        initial_cash=1_000,
        evaluated_at=_now(),
    )


def _authorization(
    root,
    *,
    scopes: tuple[SemanticTargetActivationScope, ...] = (
        SemanticTargetActivationScope.DRY_RUN,
        SemanticTargetActivationScope.SEMANTIC_PAPER,
    ),
    valid_until=None,
):
    rehearsal_root = root / "rehearsal"
    report = run_semantic_target_local_rehearsal(
        rehearsal_id="activated-rehearsal-1",
        output_root=rehearsal_root,
        evaluated_at=_now(),
    )
    report_path = rehearsal_root / "reports" / f"{report.rehearsal_id}.json"
    authorization = SemanticTargetActivationAuthorization(
        authorization_id="authorization-1",
        revision=1,
        allowed_scopes=scopes,
        orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
        rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
        rehearsal_id=report.rehearsal_id,
        rehearsal_report_sha256=rehearsal_report_sha256(report_path),
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=valid_until or _now() + timedelta(days=1),
        issued_by="test-operator",
        reason="reviewed activated workflow",
        evidence_refs=("review:test",),
    )
    return report_path, authorization


def _decision() -> StrategyTargetDecision:
    return StrategyTargetDecision(
        decision_id="decision-1",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id="bars-sha256",
        generated_at=_now(),
        effective_at=_now(),
        valid_until=_now() + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled target",
    )


def _evaluation() -> StrategyEvaluation:
    return StrategyEvaluation(
        evaluation_id="strategy-evaluation-1",
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        evaluated_at=_now(),
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id="decision-1",
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
        reconciliation_policy_version=ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _account() -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        id="dry-account-1",
        broker_name="local-dry-run",
        account_id="local-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        captured_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 6, 13, 12, tzinfo=UTC)
