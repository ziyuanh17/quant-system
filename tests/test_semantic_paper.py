from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    SemanticPaperBrokerAdapter,
    SemanticPaperBrokerClient,
    append_execution_event,
    claim_execution_plan,
    current_execution_status,
    load_execution_events,
    run_semantic_target_paper,
)
from quant.models.execution import (
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    Position,
    SemanticPaperBrokerState,
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
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.research import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)


def test_semantic_paper_client_persists_idempotent_order(tmp_path) -> None:
    state_path = tmp_path / "state.json"
    client = SemanticPaperBrokerClient(
        state_path=state_path,
        initial_cash=1_000,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)

    first = client.submit_market_order(
        request,
        reference_price=100,
        client_order_id="order-1",
        safety_check=_paper_check(),
    )
    restarted = SemanticPaperBrokerClient(
        state_path=state_path,
        initial_cash=1_000,
    )
    second = restarted.submit_market_order(
        request,
        reference_price=100,
        client_order_id="order-1",
        safety_check=_paper_check(),
    )

    assert second == first
    assert restarted.account_snapshot().cash == 800
    assert len(restarted.fills()) == 1
    assert (
        SemanticPaperBrokerState.model_validate_json(
            state_path.read_text()
        ).order_sequence
        == 1
    )


def test_semantic_paper_client_supports_short_cover_and_reversal(
    tmp_path,
) -> None:
    client = SemanticPaperBrokerClient(
        state_path=tmp_path / "state.json",
        initial_cash=1_000,
    )

    client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        reference_price=100,
        client_order_id="short",
        safety_check=_paper_check(),
    )
    assert client.account_snapshot().positions[0].quantity == -2
    assert client.account_snapshot().cash == 1_200

    client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
        reference_price=90,
        client_order_id="cover",
        safety_check=_paper_check(),
    )
    assert client.account_snapshot().positions[0].quantity == -1

    client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=3),
        reference_price=95,
        client_order_id="reverse",
        safety_check=_paper_check(),
    )
    position = client.account_snapshot().positions[0]
    assert position.quantity == 2
    assert position.average_price == 95


def test_semantic_paper_adapter_rejects_non_paper_safety(tmp_path) -> None:
    adapter = SemanticPaperBrokerAdapter(
        client=SemanticPaperBrokerClient(
            state_path=tmp_path / "state.json",
            initial_cash=1_000,
        )
    )

    with pytest.raises(ValueError, match="allowed paper check"):
        adapter.submit_market_order(
            OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
            reference_price=100,
            client_order_id="wrong-mode",
            safety_check=TradingSafetyCheck(
                mode=TradingMode.LIVE,
                allowed=True,
            ),
        )


def test_semantic_paper_workflow_reaches_reconciled_satisfaction(
    tmp_path,
) -> None:
    source = _source(target_value=Decimal("-2"))

    result = _run(source, tmp_path)

    assert result.status == ExecutionPlanStatus.SATISFIED
    assert result.reconciliation is not None
    assert result.reconciliation.passed
    assert [
        event.new_status
        for event in load_execution_events(
            tmp_path / "lifecycle",
            result.plan.execution_plan_id,
        )
    ] == [
        ExecutionPlanStatus.SUBMISSION_PENDING,
        ExecutionPlanStatus.SUBMITTED,
        ExecutionPlanStatus.FILLED,
        ExecutionPlanStatus.SATISFIED,
    ]
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert state.positions[0].quantity == -2
    assert len(state.orders) == 1
    assert len(state.fills) == 1


def test_semantic_paper_workflow_restart_does_not_duplicate_order(
    tmp_path,
) -> None:
    source = _source()

    first = _run(source, tmp_path)
    second = _run(source, tmp_path)

    assert first.status == ExecutionPlanStatus.SATISFIED
    assert second.status == ExecutionPlanStatus.SATISFIED
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert len(state.orders) == 1
    assert len(state.fills) == 1
    assert (
        current_execution_status(
            second.plan,
            tmp_path / "lifecycle",
        )
        == ExecutionPlanStatus.SATISFIED
    )


def test_semantic_paper_workflow_executes_target_reversal(tmp_path) -> None:
    first = _run(_source(target_value=Decimal("-2"), revision=1), tmp_path)
    second = _run(_source(target_value=Decimal("3"), revision=2), tmp_path)

    assert first.status == ExecutionPlanStatus.SATISFIED
    assert second.status == ExecutionPlanStatus.SATISFIED
    assert second.plan.order_request is not None
    assert second.plan.order_request.side == OrderSide.BUY
    assert second.plan.order_request.quantity == 5
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert state.positions[0].quantity == 3
    assert len(state.orders) == 2
    assert len(state.fills) == 2
    assert len(tuple((tmp_path / "reconciliations").rglob("*.json"))) == 2


def test_semantic_paper_workflow_satisfies_matching_target_without_order(
    tmp_path,
) -> None:
    result = _run(
        _source(target_value=Decimal("2")),
        tmp_path,
        initial_positions=(
            Position(
                symbol="AAPL",
                quantity=2,
                average_price=100,
                last_price=100,
            ),
        ),
    )

    assert result.status == ExecutionPlanStatus.SATISFIED
    assert result.plan.order_request is None
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert state.positions[0].quantity == 2
    assert state.orders == ()
    assert state.fills == ()


def test_semantic_paper_workflow_recovers_fill_artifacts_after_crash(
    tmp_path,
) -> None:
    source = _source()
    contributor_set, _, portfolio_target, _, risk_target = source
    client = SemanticPaperBrokerClient(
        state_path=tmp_path / "state.json",
        initial_cash=1_000,
    )
    plan = claim_execution_plan(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        account=client.account_snapshot(),
        policy=_policy(),
        artifact_root=tmp_path / "lifecycle",
        created_at=_now(),
    )
    append_execution_event(
        plan=plan,
        artifact_root=tmp_path / "lifecycle",
        new_status=ExecutionPlanStatus.SUBMISSION_PENDING,
        occurred_at=_now(),
        reason="simulated crash boundary",
    )
    assert plan.order_request is not None
    client.submit_market_order(
        plan.order_request,
        reference_price=100,
        client_order_id=plan.client_order_id,
        safety_check=_paper_check(),
    )
    assert not (tmp_path / "orders").exists()
    assert not (tmp_path / "fills").exists()

    result = _run(source, tmp_path)

    assert result.status == ExecutionPlanStatus.SATISFIED
    assert len(tuple((tmp_path / "orders").glob("*.json"))) == 1
    assert len(tuple((tmp_path / "fills").glob("*.json"))) == 1
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert len(state.fills) == 1


def test_semantic_paper_workflow_rejects_insufficient_cash(tmp_path) -> None:
    source = _source(target_value=Decimal("20"))

    result = _run(source, tmp_path, initial_cash=1_000)

    assert result.status == ExecutionPlanStatus.REJECTED
    assert result.reconciliation is None
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "state.json").read_text()
    )
    assert state.orders[0].status == LiveOrderStatus.REJECTED
    assert state.fills == ()
    assert state.positions == ()


def test_semantic_paper_workflow_blocks_wrong_safety_mode(tmp_path) -> None:
    source = _source()
    contributor_set, decisions, portfolio_target, risk_policy, risk_target = (
        source
    )

    result = run_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        policy=_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.LIVE,
            allowed=True,
        ),
        state_path=tmp_path / "state.json",
        artifact_root=tmp_path / "lifecycle",
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        initial_cash=1_000,
        evaluated_at=_now(),
    )

    assert result.status == ExecutionPlanStatus.BLOCKED
    assert not (tmp_path / "orders").exists()
    assert not (tmp_path / "fills").exists()


def _run(
    source,
    root,
    *,
    initial_cash: float = 1_000,
    initial_positions: tuple[Position, ...] = (),
):
    contributor_set, decisions, portfolio_target, risk_policy, risk_target = (
        source
    )
    return run_semantic_target_paper(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        policy=_policy(),
        reference_price=100,
        safety_check=_paper_check(),
        state_path=root / "state.json",
        artifact_root=root / "lifecycle",
        order_output_dir=root / "orders",
        fill_output_dir=root / "fills",
        snapshot_output_dir=root / "snapshots",
        reconciliation_output_dir=root / "reconciliations",
        initial_cash=initial_cash,
        initial_positions=initial_positions,
        evaluated_at=_now(),
    )


def _source(
    target_value: Decimal = Decimal("2"),
    *,
    revision: int = 1,
):
    decision = StrategyTargetDecision(
        decision_id=f"decision-{revision}",
        revision=revision,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target_value,
        sizing_policy_version="fixed_shares_v1",
        input_data_id="bars-sha256",
        generated_at=_now(),
        effective_at=_now(),
        valid_until=_now() + timedelta(days=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="research target",
    )
    contributor_set = ContributorSet(
        contributor_set_id="aapl-v1",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="research ownership",
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id=f"portfolio-{revision}",
        revision=revision,
        contributor_set=contributor_set,
        decisions=(decision,),
        evaluated_at=_now(),
    )
    risk_policy = ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("100"),
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-1",
        revision=revision,
        portfolio_target=portfolio_target,
        policy=risk_policy,
        evaluated_at=_now(),
    )
    return (
        contributor_set,
        (decision,),
        portfolio_target,
        risk_policy,
        risk_target,
    )


def _paper_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.PAPER, allowed=True)


def _policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _now() -> datetime:
    return datetime(2026, 6, 12, 12, tzinfo=UTC)
