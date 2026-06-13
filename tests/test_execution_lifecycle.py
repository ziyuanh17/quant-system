from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    FakeLiveBrokerClient,
    LiveBrokerAdapter,
    claim_execution_plan,
    confirm_execution_satisfaction,
    current_execution_status,
    load_execution_drift_observation,
    load_execution_events,
    observe_execution_drift,
    reconcile_live_state,
    recover_execution_submission,
    submit_execution_plan,
)
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderRequest,
    Position,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    BrokerLookupOutcome,
    ExecutionDriftStatus,
    ExecutionLifecyclePolicy,
    ExecutionPlan,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    PortfolioTargetDecision,
    ResearchRiskPolicy,
    RiskTargetDecision,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.research import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)


def test_execution_plan_claim_is_atomic_per_risk_target(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)

    first = _claim(source, broker, tmp_path)

    assert first.execution_plan_id == "execution-risk-1"
    assert first.order_request is not None
    assert first.order_request.quantity == 2
    with pytest.raises(FileExistsError):
        _claim(source, broker, tmp_path)


def test_concurrent_execution_plan_claims_create_exactly_one_plan(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)

    def attempt_claim():
        try:
            return _claim(source, broker, tmp_path)
        except Exception as exc:
            return exc

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(executor.map(lambda _: attempt_claim(), range(2)))

    assert (
        len([item for item in results if isinstance(item, ExecutionPlan)]) == 1
    )
    assert len([item for item in results if isinstance(item, Exception)]) == 1


def test_fake_broker_lifecycle_reaches_reconciled_satisfaction(
    tmp_path,
) -> None:
    source = _source()
    broker, adapter, paths = _broker_with_artifacts(tmp_path)
    plan = _claim(source, broker, tmp_path)

    status = _submit(plan, source, adapter, tmp_path)

    assert status == ExecutionPlanStatus.FILLED
    adapter.account_snapshot()
    reconciliation = reconcile_live_state(
        client=broker,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )
    satisfied = confirm_execution_satisfaction(
        plan=plan,
        broker=broker,
        reconciliation=reconciliation,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert reconciliation.passed
    assert satisfied == ExecutionPlanStatus.SATISFIED
    assert current_execution_status(plan, tmp_path) == (
        ExecutionPlanStatus.SATISFIED
    )
    assert [
        event.new_status
        for event in load_execution_events(tmp_path, plan.execution_plan_id)
    ] == [
        ExecutionPlanStatus.SUBMISSION_PENDING,
        ExecutionPlanStatus.SUBMITTED,
        ExecutionPlanStatus.FILLED,
        ExecutionPlanStatus.SATISFIED,
    ]


def test_submit_then_crash_recovers_without_duplicate_order(tmp_path) -> None:
    source = _source()
    broker, adapter, _ = _broker_with_artifacts(tmp_path)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        _SubmitThenRaiseBroker(adapter),
        tmp_path,
    )
    evidence = recover_execution_submission(
        plan=plan,
        broker=broker,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert status == ExecutionPlanStatus.AMBIGUOUS
    assert evidence.outcome == BrokerLookupOutcome.FOUND
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.FILLED
    )
    assert len(broker.fills()) == 1


def test_not_found_recovery_blocks_without_resubmission(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        _RaiseBeforeSubmitBroker(broker),
        tmp_path,
    )
    evidence = recover_execution_submission(
        plan=plan,
        broker=broker,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert status == ExecutionPlanStatus.AMBIGUOUS
    assert evidence.outcome == BrokerLookupOutcome.NOT_FOUND
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.BLOCKED
    )
    assert broker.fills() == ()


@pytest.mark.parametrize("lookup_kind", ["unavailable", "conflicting"])
def test_uncertain_recovery_outcomes_block_without_resubmission(
    tmp_path,
    lookup_kind: str,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    assert (
        _submit(
            plan,
            source,
            _RaiseBeforeSubmitBroker(broker),
            tmp_path,
        )
        == ExecutionPlanStatus.AMBIGUOUS
    )
    recovery_broker = (
        _UnavailableLookupBroker(broker)
        if lookup_kind == "unavailable"
        else _ConflictingLookupBroker(
            broker,
            (
                _lookup_order(plan, "conflict-1"),
                _lookup_order(plan, "conflict-2"),
            ),
        )
    )

    evidence = recover_execution_submission(
        plan=plan,
        broker=recovery_broker,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert evidence.outcome.value == lookup_kind
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.BLOCKED
    )
    assert broker.fills() == ()


def test_pre_submission_revalidation_blocks_stale_strategy_target(
    tmp_path,
) -> None:
    source = _source(max_age_seconds=60)
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        broker,
        tmp_path,
        evaluated_at=_now() + timedelta(minutes=2),
    )

    assert status == ExecutionPlanStatus.BLOCKED
    assert broker.fills() == ()
    assert (
        "revalidation changed"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


def test_pre_submission_revalidation_blocks_working_orders(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        _WorkingOrderBroker(broker),
        tmp_path,
    )

    assert status == ExecutionPlanStatus.BLOCKED
    assert (
        "unsettled working orders"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )
    assert broker.fills() == ()


def test_pre_submission_revalidation_blocks_invalid_safety_check(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        broker,
        tmp_path,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
    )

    assert status == ExecutionPlanStatus.BLOCKED
    assert [
        event.new_status
        for event in load_execution_events(tmp_path, plan.execution_plan_id)
    ] == [ExecutionPlanStatus.BLOCKED]
    assert broker.fills() == ()


def test_failed_account_wide_reconciliation_prevents_satisfaction(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    assert _submit(plan, source, broker, tmp_path) == ExecutionPlanStatus.FILLED
    failed = LiveReconciliationReport(
        broker_name="fake-live",
        account_id="fake-account",
        broker_environment="paper",
        local_order_count=0,
        broker_order_count=0,
        local_fill_count=0,
        broker_fill_count=1,
        local_position_count=0,
        broker_position_count=1,
        status=LiveReconciliationStatus.FAILED,
    )

    status = confirm_execution_satisfaction(
        plan=plan,
        broker=broker,
        reconciliation=failed,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert status == ExecutionPlanStatus.FILLED
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.FILLED
    )
    assert (
        "account-wide reconciliation failed"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


def test_reconciliation_for_another_account_prevents_satisfaction(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    assert _submit(plan, source, broker, tmp_path) == ExecutionPlanStatus.FILLED
    wrong_account = LiveReconciliationReport(
        broker_name="fake-live",
        account_id="another-account",
        broker_environment="paper",
        local_order_count=0,
        broker_order_count=0,
        local_fill_count=1,
        broker_fill_count=1,
        local_position_count=1,
        broker_position_count=1,
        status=LiveReconciliationStatus.PASSED,
    )

    status = confirm_execution_satisfaction(
        plan=plan,
        broker=broker,
        reconciliation=wrong_account,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert status == ExecutionPlanStatus.FILLED
    assert (
        "another account"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


def test_stale_reconciliation_evidence_prevents_satisfaction(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    assert _submit(plan, source, broker, tmp_path) == ExecutionPlanStatus.FILLED
    stale = LiveReconciliationReport(
        broker_name="fake-live",
        account_id="fake-account",
        broker_environment="paper",
        local_order_count=0,
        broker_order_count=0,
        local_fill_count=1,
        broker_fill_count=1,
        local_position_count=1,
        broker_position_count=1,
        status=LiveReconciliationStatus.PASSED,
        created_at=_now() - timedelta(minutes=1),
    )

    status = confirm_execution_satisfaction(
        plan=plan,
        broker=broker,
        reconciliation=stale,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert status == ExecutionPlanStatus.FILLED
    assert (
        "predates execution"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


def test_rejected_order_does_not_satisfy_target(tmp_path) -> None:
    source = _source(target_value=Decimal("-1"))
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(plan, source, broker, tmp_path)

    assert status == ExecutionPlanStatus.REJECTED
    with pytest.raises(ValueError, match="not eligible"):
        confirm_execution_satisfaction(
            plan=plan,
            broker=broker,
            reconciliation=LiveReconciliationReport(
                broker_name="fake-live",
                account_id="fake-account",
                broker_environment="paper",
                local_order_count=0,
                broker_order_count=0,
                local_fill_count=0,
                broker_fill_count=0,
                local_position_count=0,
                broker_position_count=0,
                status=LiveReconciliationStatus.PASSED,
            ),
            artifact_root=tmp_path,
            evaluated_at=_now() + timedelta(minutes=1),
        )


def test_detect_only_drift_observation_never_repairs_position(tmp_path) -> None:
    source = _source()
    broker, adapter, paths = _broker_with_artifacts(tmp_path)
    plan = _claim(source, broker, tmp_path)
    assert (
        _submit(plan, source, adapter, tmp_path) == ExecutionPlanStatus.FILLED
    )
    adapter.account_snapshot()
    reconciliation = reconcile_live_state(
        client=broker,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )
    assert (
        confirm_execution_satisfaction(
            plan=plan,
            broker=broker,
            reconciliation=reconciliation,
            artifact_root=tmp_path,
            evaluated_at=_now() + timedelta(minutes=1),
        )
        == ExecutionPlanStatus.SATISFIED
    )
    drifted_broker = FakeLiveBrokerClient(
        initial_cash=1_000,
        positions=(
            Position(
                symbol="AAPL",
                quantity=1,
                average_price=100,
                last_price=100,
            ),
        ),
    )

    observation = observe_execution_drift(
        plan=plan,
        broker=drifted_broker,
        artifact_root=tmp_path,
        observed_at=_now() + timedelta(minutes=2),
    )
    observation_path = (
        tmp_path
        / "drift-observations"
        / plan.execution_plan_id
        / f"{observation.observation_id}.json"
    )

    assert observation.status == ExecutionDriftStatus.DETECTED
    assert load_execution_drift_observation(observation_path) == observation
    assert current_execution_status(plan, tmp_path) == (
        ExecutionPlanStatus.SATISFIED
    )
    assert drifted_broker.fills() == ()


def test_fractional_risk_target_cannot_claim_operational_plan(tmp_path) -> None:
    source = _source(target_value=Decimal("1.5"))
    broker = FakeLiveBrokerClient(initial_cash=1_000)

    with pytest.raises(ValueError, match="rejects fractional shares"):
        _claim(source, broker, tmp_path)


class _SubmitThenRaiseBroker:
    def __init__(self, delegate) -> None:
        self.delegate = delegate

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        self.delegate.submit_market_order(
            request,
            reference_price=reference_price,
            client_order_id=client_order_id,
            safety_check=safety_check,
        )
        raise RuntimeError("connection lost after broker accepted order")

    def account_snapshot(self):
        return self.delegate.account_snapshot()

    def has_open_orders(self) -> bool:
        return self.delegate.has_open_orders()

    def orders_by_client_order_id(
        self, client_order_id: str
    ) -> tuple[LiveOrderRecord, ...]:
        return self.delegate.orders_by_client_order_id(client_order_id)


class _RaiseBeforeSubmitBroker(_SubmitThenRaiseBroker):
    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        raise RuntimeError("connection lost before broker visibility")


class _UnavailableLookupBroker(_RaiseBeforeSubmitBroker):
    def orders_by_client_order_id(
        self, client_order_id: str
    ) -> tuple[LiveOrderRecord, ...]:
        raise RuntimeError("lookup service unavailable")


class _ConflictingLookupBroker(_RaiseBeforeSubmitBroker):
    def __init__(
        self,
        delegate,
        orders: tuple[LiveOrderRecord, ...],
    ) -> None:
        super().__init__(delegate)
        self.orders = orders

    def orders_by_client_order_id(
        self, client_order_id: str
    ) -> tuple[LiveOrderRecord, ...]:
        return self.orders


class _WorkingOrderBroker(_RaiseBeforeSubmitBroker):
    def has_open_orders(self) -> bool:
        return True


def _lookup_order(plan: ExecutionPlan, record_id: str) -> LiveOrderRecord:
    assert plan.order_request is not None
    return LiveOrderRecord(
        id=record_id,
        client_order_id=plan.client_order_id,
        broker_order_id=f"broker-{record_id}",
        broker_name="fake-live",
        account_id="fake-account",
        broker_environment="paper",
        request=plan.order_request,
        reference_price=100,
        notional=plan.order_request.quantity * 100,
        safety_check=TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True),
        status=LiveOrderStatus.ACCEPTED,
    )


def _submit(
    plan,
    source,
    broker,
    artifact_root,
    *,
    evaluated_at: datetime | None = None,
    safety_check: TradingSafetyCheck | None = None,
) -> ExecutionPlanStatus:
    contributor_set, decisions, portfolio_target, risk_policy, risk_target = (
        source
    )
    return submit_execution_plan(
        plan=plan,
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        broker=broker,
        reference_price=100,
        safety_check=safety_check
        or TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True),
        artifact_root=artifact_root,
        evaluated_at=evaluated_at or _now(),
    )


def _claim(source, broker, artifact_root):
    contributor_set, _, portfolio_target, _, risk_target = source
    return claim_execution_plan(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        account=broker.account_snapshot(),
        policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        artifact_root=artifact_root,
        created_at=_now(),
    )


def _source(
    *,
    target_value: Decimal = Decimal("2"),
    max_age_seconds: int = 3600,
) -> tuple[
    ContributorSet,
    tuple[StrategyTargetDecision, ...],
    PortfolioTargetDecision,
    ResearchRiskPolicy,
    RiskTargetDecision,
]:
    decision = StrategyTargetDecision(
        decision_id="decision-1",
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
        max_age_seconds=max_age_seconds,
        portfolio_policy_version="sum_active_targets_v1",
        reason="research ownership",
    )
    portfolio_target = aggregate_strategy_targets(
        portfolio_target_id="portfolio-1",
        revision=1,
        contributor_set=contributor_set,
        decisions=(decision,),
        evaluated_at=_now(),
    )
    risk_policy = ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("10"),
    )
    risk_target = evaluate_research_risk_target(
        risk_target_id="risk-1",
        revision=1,
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


def _broker_with_artifacts(tmp_path):
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    paths = {
        "orders": tmp_path / "broker" / "orders",
        "fills": tmp_path / "broker" / "fills",
        "snapshots": tmp_path / "broker" / "snapshots",
    }
    return (
        broker,
        LiveBrokerAdapter(
            client=broker,
            order_output_dir=paths["orders"],
            fill_output_dir=paths["fills"],
            snapshot_output_dir=paths["snapshots"],
        ),
        paths,
    )


def _now() -> datetime:
    return datetime(2026, 6, 12, 12, tzinfo=UTC)
