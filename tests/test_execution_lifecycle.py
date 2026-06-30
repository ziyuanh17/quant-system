"""Test execution lifecycle behavior and safety invariants."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from pydantic import ValidationError

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    FakeLiveBrokerClient,
    LiveBrokerAdapter,
    append_execution_leg_event,
    build_execution_transition_plan,
    claim_execution_plan,
    confirm_execution_satisfaction,
    current_execution_leg_status,
    current_execution_status,
    execution_plan_path,
    execution_transition_plan_path,
    load_execution_drift_observation,
    load_execution_events,
    load_execution_leg_events,
    load_execution_plan,
    load_execution_transition_plan,
    load_live_order_records,
    observe_execution_drift,
    plan_target_transition_orders,
    reconcile_live_state,
    recover_execution_submission,
    refresh_submitted_execution,
    run_fake_multi_leg_transition,
    submit_execution_plan,
    target_transition_crosses_zero,
    write_execution_transition_plan,
)
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderRequest,
    OrderSide,
    Position,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    BrokerLookupOutcome,
    ExecutionDriftStatus,
    ExecutionLegStatus,
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

    assert first.execution_plan_id == "execution-risk-1-r1"
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


def test_distinct_risk_target_revisions_claim_distinct_plans(tmp_path) -> None:
    first_source = _source(risk_target_revision=1)
    second_source = _source(risk_target_revision=2)
    broker = FakeLiveBrokerClient(initial_cash=1_000)

    first = _claim(first_source, broker, tmp_path)
    second = _claim(second_source, broker, tmp_path)

    assert first.execution_plan_id == "execution-risk-1-r1"
    assert second.execution_plan_id == "execution-risk-1-r2"
    assert first.client_order_id != second.client_order_id


@pytest.mark.parametrize(
    ("current", "target", "expected"),
    [
        (0, 2, ((OrderSide.BUY, 2),)),
        (1, 3, ((OrderSide.BUY, 2),)),
        (3, 1, ((OrderSide.SELL, 2),)),
        (3, 0, ((OrderSide.SELL, 3),)),
        (-3, 0, ((OrderSide.BUY, 3),)),
        (-1, -3, ((OrderSide.SELL, 2),)),
        (-3, -1, ((OrderSide.BUY, 2),)),
        (-1, 2, ((OrderSide.BUY, 1), (OrderSide.BUY, 2))),
        (2, -1, ((OrderSide.SELL, 2), (OrderSide.SELL, 1))),
    ],
)
def test_target_transition_planner_preserves_reversal_legs(
    current: int,
    target: int,
    expected: tuple[tuple[OrderSide, int], ...],
) -> None:
    orders = plan_target_transition_orders(
        symbol="AAPL",
        current_quantity=current,
        target_quantity=target,
    )

    assert tuple((order.side, order.quantity) for order in orders) == expected
    assert all(order.symbol == "AAPL" for order in orders)


def test_target_transition_planner_detects_only_cross_zero_reversal() -> None:
    assert target_transition_crosses_zero(-1, 2)
    assert target_transition_crosses_zero(2, -1)
    assert not target_transition_crosses_zero(0, 2)
    assert not target_transition_crosses_zero(-2, 0)
    assert not target_transition_crosses_zero(1, 3)


def test_execution_transition_plan_records_reversal_legs(tmp_path) -> None:
    source = _source(target_value=Decimal("2"))
    broker = FakeLiveBrokerClient(
        initial_cash=1_000,
        positions=(
            Position(
                symbol="AAPL",
                quantity=-1,
                average_price=100,
                last_price=100,
            ),
        ),
    )
    plan = _claim(source, broker, tmp_path)

    transition = build_execution_transition_plan(
        plan=plan,
        created_at=_now(),
    )
    path = write_execution_transition_plan(transition, tmp_path)
    loaded = load_execution_transition_plan(path)

    assert path == execution_transition_plan_path(
        tmp_path,
        plan.execution_plan_id,
    )
    assert loaded == transition
    assert loaded.transition_plan_id == f"transition-{plan.execution_plan_id}"
    assert [(leg.semantic, leg.client_order_id) for leg in loaded.legs] == [
        ("close_short", f"{plan.client_order_id}-leg-1"),
        ("open_long", f"{plan.client_order_id}-leg-2"),
    ]
    assert [
        (leg.order_request.side, leg.order_request.quantity)
        for leg in loaded.legs
    ] == [(OrderSide.BUY, 1), (OrderSide.BUY, 2)]
    assert [
        (leg.required_start_quantity, leg.required_end_quantity)
        for leg in loaded.legs
    ] == [(-1, 0), (0, 2)]


def test_execution_transition_plan_write_is_immutable(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    transition = build_execution_transition_plan(
        plan=plan,
        created_at=_now(),
    )

    write_execution_transition_plan(transition, tmp_path)

    with pytest.raises(FileExistsError):
        write_execution_transition_plan(transition, tmp_path)


def test_execution_transition_plan_schema_fails_closed(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    transition = build_execution_transition_plan(
        plan=plan,
        created_at=_now(),
    )
    path = write_execution_transition_plan(transition, tmp_path)
    payload = json.loads(path.read_text())
    payload["schema_version"] = 1
    legacy_path = tmp_path / "legacy-transition.json"
    legacy_path.write_text(json.dumps(payload))

    with pytest.raises(ValidationError, match="schema_version"):
        load_execution_transition_plan(legacy_path)


def test_execution_transition_plan_allows_satisfied_noop(tmp_path) -> None:
    source = _source(target_value=Decimal("0"))
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    transition = build_execution_transition_plan(
        plan=plan,
        created_at=_now(),
    )

    assert transition.current_quantity == 0
    assert transition.target_quantity == 0
    assert transition.legs == ()


def test_execution_leg_events_append_and_report_current_status(
    tmp_path,
) -> None:
    transition = _write_reversal_transition(tmp_path)
    leg_id = transition.legs[0].leg_id

    assert (
        current_execution_leg_status(transition, tmp_path, leg_id)
        == ExecutionLegStatus.PLANNED
    )

    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.SUBMISSION_PENDING,
        occurred_at=_now(),
        reason="leg submission intent recorded",
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.SUBMITTED,
        occurred_at=_now() + timedelta(seconds=1),
        reason="leg order submitted",
        broker_order_ids=("broker-leg-1",),
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.FILLED,
        occurred_at=_now() + timedelta(seconds=2),
        reason="leg order filled",
        broker_order_ids=("broker-leg-1",),
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.RECONCILED,
        occurred_at=_now() + timedelta(seconds=3),
        reason="leg position reconciled",
        broker_order_ids=("broker-leg-1",),
    )

    assert [
        event.new_status
        for event in load_execution_leg_events(
            tmp_path,
            transition.transition_plan_id,
            leg_id,
        )
    ] == [
        ExecutionLegStatus.SUBMISSION_PENDING,
        ExecutionLegStatus.SUBMITTED,
        ExecutionLegStatus.FILLED,
        ExecutionLegStatus.RECONCILED,
    ]
    assert (
        current_execution_leg_status(transition, tmp_path, leg_id)
        == ExecutionLegStatus.RECONCILED
    )


def test_execution_leg_events_reject_invalid_transition(tmp_path) -> None:
    transition = _write_reversal_transition(tmp_path)
    leg_id = transition.legs[0].leg_id

    with pytest.raises(ValueError, match="invalid execution leg transition"):
        append_execution_leg_event(
            transition=transition,
            artifact_root=tmp_path,
            leg_id=leg_id,
            new_status=ExecutionLegStatus.FILLED,
            occurred_at=_now(),
            reason="cannot fill before submission",
        )


def test_execution_leg_events_reject_broker_order_id_swap(tmp_path) -> None:
    transition = _write_reversal_transition(tmp_path)
    leg_id = transition.legs[0].leg_id
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.SUBMISSION_PENDING,
        occurred_at=_now(),
        reason="leg submission intent recorded",
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.SUBMITTED,
        occurred_at=_now() + timedelta(seconds=1),
        reason="leg order submitted",
        broker_order_ids=("broker-leg-1",),
    )

    with pytest.raises(ValueError, match="another broker order"):
        append_execution_leg_event(
            transition=transition,
            artifact_root=tmp_path,
            leg_id=leg_id,
            new_status=ExecutionLegStatus.FILLED,
            occurred_at=_now() + timedelta(seconds=2),
            reason="conflicting leg fill",
            broker_order_ids=("broker-leg-2",),
        )


def test_execution_leg_events_detect_tampered_status_chain(tmp_path) -> None:
    transition = _write_reversal_transition(tmp_path)
    leg_id = transition.legs[0].leg_id
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.SUBMISSION_PENDING,
        occurred_at=_now(),
        reason="leg submission intent recorded",
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=tmp_path,
        leg_id=leg_id,
        new_status=ExecutionLegStatus.BLOCKED,
        occurred_at=_now() + timedelta(seconds=1),
        reason="leg blocked before broker order",
    )
    second_path = (
        tmp_path
        / "leg-events"
        / transition.transition_plan_id
        / leg_id
        / "000002.json"
    )
    payload = json.loads(second_path.read_text())
    payload["previous_status"] = ExecutionLegStatus.SUBMITTED.value
    second_path.write_text(json.dumps(payload))

    with pytest.raises(ValueError, match="status chain"):
        load_execution_leg_events(
            tmp_path,
            transition.transition_plan_id,
            leg_id,
        )


def test_fake_multi_leg_transition_reconciles_short_to_long_reversal(
    tmp_path,
) -> None:
    transition = _write_reversal_transition(tmp_path)
    broker = FakeLiveBrokerClient(
        initial_cash=1_000,
        positions=(
            Position(
                symbol="AAPL",
                quantity=-1,
                average_price=100,
                last_price=100,
            ),
        ),
    )

    result = run_fake_multi_leg_transition(
        transition=transition,
        broker_client=broker,
        artifact_root=tmp_path,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_live_check(),
        evaluated_at=_now(),
    )

    assert result.leg_statuses == (
        ExecutionLegStatus.RECONCILED,
        ExecutionLegStatus.RECONCILED,
    )
    assert all(
        reconciliation.passed for reconciliation in result.reconciliations
    )
    assert [
        position.quantity for position in broker.account_snapshot().positions
    ] == [2]
    assert [
        order.client_order_id
        for order in load_live_order_records(tmp_path / "orders")
    ] == [
        transition.legs[0].client_order_id,
        transition.legs[1].client_order_id,
    ]
    assert len(tuple((tmp_path / "reconciliations").rglob("*.json"))) == 2


def test_fake_multi_leg_transition_restart_skips_reconciled_legs(
    tmp_path,
) -> None:
    transition = _write_reversal_transition(tmp_path)
    broker = FakeLiveBrokerClient(
        initial_cash=1_000,
        positions=(
            Position(
                symbol="AAPL",
                quantity=-1,
                average_price=100,
                last_price=100,
            ),
        ),
    )

    first = run_fake_multi_leg_transition(
        transition=transition,
        broker_client=broker,
        artifact_root=tmp_path,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_live_check(),
        evaluated_at=_now(),
    )
    second = run_fake_multi_leg_transition(
        transition=transition,
        broker_client=broker,
        artifact_root=tmp_path,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_live_check(),
        evaluated_at=_now() + timedelta(seconds=10),
    )

    assert first.leg_statuses == second.leg_statuses
    assert len(load_live_order_records(tmp_path / "orders")) == 2
    assert len(broker.fills()) == 2


def test_fake_multi_leg_transition_blocks_on_start_quantity_mismatch(
    tmp_path,
) -> None:
    transition = _write_reversal_transition(tmp_path)
    broker = FakeLiveBrokerClient(initial_cash=1_000)

    result = run_fake_multi_leg_transition(
        transition=transition,
        broker_client=broker,
        artifact_root=tmp_path,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_live_check(),
        evaluated_at=_now(),
    )

    assert result.leg_statuses == (
        ExecutionLegStatus.BLOCKED,
        ExecutionLegStatus.PLANNED,
    )
    assert load_live_order_records(tmp_path / "orders") == ()
    assert broker.fills() == ()


def test_v1_execution_plan_artifact_fails_closed(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    _claim(source, broker, tmp_path)
    path = execution_plan_path(tmp_path, "risk-1", 1)
    payload = json.loads(path.read_text())
    payload["schema_version"] = 1
    legacy_path = tmp_path / "legacy-v1-plan.json"
    legacy_path.write_text(json.dumps(payload))

    with pytest.raises(ValidationError, match="schema_version"):
        load_execution_plan(legacy_path)


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


def test_submission_response_identity_mismatch_becomes_ambiguous(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)

    status = _submit(
        plan,
        source,
        _MismatchedSubmissionBroker(broker, plan),
        tmp_path,
    )

    assert status == ExecutionPlanStatus.AMBIGUOUS
    assert (
        "identity mismatch"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


def test_submitted_order_refresh_reaches_terminal_fill(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    delayed = _AcceptedThenFilledBroker(broker, plan)

    assert (
        _submit(plan, source, delayed, tmp_path)
        == ExecutionPlanStatus.SUBMITTED
    )

    evidence = refresh_submitted_execution(
        plan=plan,
        broker=delayed,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert evidence.outcome == BrokerLookupOutcome.FOUND
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.FILLED
    )


def test_submitted_order_refresh_rejects_broker_order_id_swap(tmp_path) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    delayed = _AcceptedThenFilledBroker(
        broker,
        plan,
        refreshed_broker_order_id="different-broker-order",
    )
    assert (
        _submit(plan, source, delayed, tmp_path)
        == ExecutionPlanStatus.SUBMITTED
    )

    evidence = refresh_submitted_execution(
        plan=plan,
        broker=delayed,
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert evidence.outcome == BrokerLookupOutcome.CONFLICTING
    assert evidence.order_identity_results == ("broker order ID differs",)
    assert (
        current_execution_status(plan, tmp_path)
        == ExecutionPlanStatus.AMBIGUOUS
    )


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


def test_recovery_matching_client_id_but_wrong_request_is_conflicting(
    tmp_path,
) -> None:
    source = _source()
    broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, broker, tmp_path)
    assert (
        _submit(plan, source, _RaiseBeforeSubmitBroker(broker), tmp_path)
        == ExecutionPlanStatus.AMBIGUOUS
    )

    evidence = recover_execution_submission(
        plan=plan,
        broker=_ConflictingLookupBroker(
            broker,
            (_lookup_order(plan, "wrong-request", quantity=1),),
        ),
        artifact_root=tmp_path,
        evaluated_at=_now() + timedelta(minutes=1),
    )

    assert evidence.outcome == BrokerLookupOutcome.CONFLICTING
    assert evidence.order_identity_results == ("order request differs",)
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.BLOCKED
    )


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


def test_pre_submission_revalidation_blocks_another_broker_account(
    tmp_path,
) -> None:
    source = _source()
    claimed_broker = FakeLiveBrokerClient(initial_cash=1_000)
    plan = _claim(source, claimed_broker, tmp_path)
    another_account = FakeLiveBrokerClient(
        initial_cash=1_000,
        account_id="another-account",
    )

    status = _submit(plan, source, another_account, tmp_path)

    assert status == ExecutionPlanStatus.BLOCKED
    assert (
        "account identity changed"
        in load_execution_events(tmp_path, plan.execution_plan_id)[-1].reason
    )


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


def test_drift_observation_for_another_account_is_indeterminate(
    tmp_path,
) -> None:
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

    observation = observe_execution_drift(
        plan=plan,
        broker=FakeLiveBrokerClient(
            initial_cash=1_000,
            account_id="another-account",
        ),
        artifact_root=tmp_path,
        observed_at=_now() + timedelta(minutes=2),
    )

    assert observation.status == ExecutionDriftStatus.INDETERMINATE
    assert "account identity differs" in observation.reason


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


class _MismatchedSubmissionBroker(_RaiseBeforeSubmitBroker):
    def __init__(self, delegate, plan: ExecutionPlan) -> None:
        super().__init__(delegate)
        self.plan = plan

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        return _lookup_order(self.plan, "wrong-response", quantity=1)


class _AcceptedThenFilledBroker(_RaiseBeforeSubmitBroker):
    def __init__(
        self,
        delegate,
        plan: ExecutionPlan,
        refreshed_broker_order_id: str = "delayed-broker-order",
    ) -> None:
        super().__init__(delegate)
        self.plan = plan
        self.refreshed_broker_order_id = refreshed_broker_order_id

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        return _lookup_order(
            self.plan,
            "accepted-order",
            broker_order_id="delayed-broker-order",
            status=LiveOrderStatus.ACCEPTED,
        )

    def orders_by_client_order_id(
        self, client_order_id: str
    ) -> tuple[LiveOrderRecord, ...]:
        return (
            _lookup_order(
                self.plan,
                "filled-order",
                broker_order_id=self.refreshed_broker_order_id,
                status=LiveOrderStatus.FILLED,
            ),
        )


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


def _lookup_order(
    plan: ExecutionPlan,
    record_id: str,
    *,
    quantity: int | None = None,
    broker_order_id: str | None = None,
    status: LiveOrderStatus = LiveOrderStatus.ACCEPTED,
) -> LiveOrderRecord:
    assert plan.order_request is not None
    request = (
        plan.order_request
        if quantity is None
        else plan.order_request.model_copy(update={"quantity": quantity})
    )
    return LiveOrderRecord(
        id=record_id,
        client_order_id=plan.client_order_id,
        broker_order_id=broker_order_id or f"broker-{record_id}",
        broker_name="fake-live",
        account_id="fake-account",
        broker_environment="paper",
        request=request,
        reference_price=100,
        notional=request.quantity * 100,
        safety_check=TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True),
        status=status,
    )


def _live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)


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


def _write_reversal_transition(tmp_path):
    source = _source(target_value=Decimal("2"))
    broker = FakeLiveBrokerClient(
        initial_cash=1_000,
        positions=(
            Position(
                symbol="AAPL",
                quantity=-1,
                average_price=100,
                last_price=100,
            ),
        ),
    )
    plan = _claim(source, broker, tmp_path)
    transition = build_execution_transition_plan(
        plan=plan,
        created_at=_now(),
    )
    write_execution_transition_plan(transition, tmp_path)
    return transition


def _source(
    *,
    target_value: Decimal = Decimal("2"),
    max_age_seconds: int = 3600,
    risk_target_revision: int = 1,
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
        revision=risk_target_revision,
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
