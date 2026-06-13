from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
    claim_execution_plan,
    current_execution_status,
    load_execution_dry_run_observation,
    load_execution_events,
    observe_execution_plan_dry_run,
    run_semantic_target_dry_run,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    Position,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunObservation,
    ExecutionDryRunStatus,
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
from quant.operations import LockAcquisitionError
from quant.research import (
    aggregate_strategy_targets,
    evaluate_research_risk_target,
)


def test_semantic_target_dry_run_records_would_submit_without_events(
    tmp_path,
) -> None:
    source = _source()
    account = _account()
    plan = _claim(source, account, tmp_path)

    observation = _observe(plan, source, account, tmp_path)
    path = (
        tmp_path
        / "dry-run-observations"
        / plan.execution_plan_id
        / f"{observation.observation_id}.json"
    )

    assert observation.status == ExecutionDryRunStatus.WOULD_SUBMIT
    assert observation.order_request == plan.order_request
    assert observation.notional == 200
    assert load_execution_dry_run_observation(path) == observation
    assert (
        current_execution_status(plan, tmp_path) == ExecutionPlanStatus.PLANNED
    )
    assert load_execution_events(tmp_path, plan.execution_plan_id) == ()


def test_semantic_target_dry_run_records_already_satisfied(tmp_path) -> None:
    source = _source(target_value=Decimal("2"))
    account = _account(position_quantity=2)
    plan = _claim(source, account, tmp_path)

    observation = _observe(plan, source, account, tmp_path)

    assert observation.status == ExecutionDryRunStatus.ALREADY_SATISFIED
    assert observation.order_request is None
    assert observation.notional == 0


def test_semantic_target_dry_run_records_working_order_block(tmp_path) -> None:
    source = _source()
    plan = _claim(source, _account(), tmp_path)
    account = _account(open_order_ids=("working-1",))

    observation = _observe(plan, source, account, tmp_path)

    assert observation.status == ExecutionDryRunStatus.BLOCKED
    assert (
        "broker has unsettled working orders" in observation.validation_reasons
    )


def test_semantic_target_dry_run_records_position_change_block(
    tmp_path,
) -> None:
    source = _source()
    plan = _claim(source, _account(), tmp_path)

    observation = _observe(
        plan,
        source,
        _account(position_quantity=1),
        tmp_path,
    )

    assert observation.status == ExecutionDryRunStatus.BLOCKED
    assert (
        "broker position changed after plan creation"
        in observation.validation_reasons
    )


def test_semantic_target_dry_run_is_immutable_per_plan(tmp_path) -> None:
    source = _source()
    account = _account()
    plan = _claim(source, account, tmp_path)
    _observe(plan, source, account, tmp_path)

    with pytest.raises(FileExistsError):
        _observe(plan, source, account, tmp_path)


def test_semantic_target_dry_run_requires_allowed_dry_run_check(
    tmp_path,
) -> None:
    source = _source()
    account = _account()
    plan = _claim(source, account, tmp_path)

    observation = _observe(
        plan,
        source,
        account,
        tmp_path,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=False,
            issues=("operator disabled dry-run",),
        ),
    )

    assert observation.status == ExecutionDryRunStatus.BLOCKED
    assert (
        "dry_run safety check is not allowed" in observation.validation_reasons
    )


def test_semantic_target_dry_run_persists_wrong_mode_block(tmp_path) -> None:
    source = _source()
    account = _account()
    plan = _claim(source, account, tmp_path)

    observation = _observe(
        plan,
        source,
        account,
        tmp_path,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.LIVE,
            allowed=True,
        ),
    )

    assert observation.status == ExecutionDryRunStatus.BLOCKED
    assert (
        "dry_run safety check is not allowed" in observation.validation_reasons
    )


def test_semantic_target_dry_run_persists_invalid_price_block(tmp_path) -> None:
    source = _source()
    account = _account()
    plan = _claim(source, account, tmp_path)
    (
        contributor_set,
        decisions,
        portfolio_target,
        risk_policy,
        risk_target,
    ) = source

    observation = observe_execution_plan_dry_run(
        plan=plan,
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        account=account,
        reference_price=-1,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        artifact_root=tmp_path,
        evaluated_at=_now(),
    )

    assert observation.status == ExecutionDryRunStatus.BLOCKED
    assert observation.reference_price == -1
    assert observation.notional == 0
    assert "reference price must be positive" in observation.validation_reasons


def test_semantic_target_dry_run_workflow_is_restart_idempotent(
    tmp_path,
) -> None:
    source = _source()
    account = _account()

    first = _run(source, account, tmp_path)
    second = _run(source, account, tmp_path)

    assert second == first
    assert len(tuple((tmp_path / "plans").glob("*.json"))) == 1
    assert len(tuple((tmp_path / "dry-run-observations").rglob("*.json"))) == 1


def test_semantic_target_dry_run_workflow_fails_closed_concurrently(
    tmp_path,
) -> None:
    source = _source()
    account = _account()

    with ThreadPoolExecutor(max_workers=2) as executor:

        def attempt_run(_):
            try:
                return _run(source, account, tmp_path)
            except Exception as exc:
                return exc

        results = tuple(executor.map(attempt_run, range(2)))

    assert (
        len(
            [
                result
                for result in results
                if isinstance(result, ExecutionDryRunObservation)
            ]
        )
        == 1
    )
    assert (
        len(
            [
                result
                for result in results
                if isinstance(result, LockAcquisitionError)
            ]
        )
        == 1
    )
    assert len(tuple((tmp_path / "plans").glob("*.json"))) == 1
    assert len(tuple((tmp_path / "dry-run-observations").rglob("*.json"))) == 1


def _observe(
    plan,
    source,
    account,
    artifact_root,
    *,
    safety_check: TradingSafetyCheck | None = None,
):
    (
        contributor_set,
        decisions,
        portfolio_target,
        risk_policy,
        risk_target,
    ) = source
    return observe_execution_plan_dry_run(
        plan=plan,
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        account=account,
        reference_price=100,
        safety_check=safety_check
        or TradingSafetyCheck(mode=TradingMode.DRY_RUN, allowed=True),
        artifact_root=artifact_root,
        evaluated_at=_now(),
    )


def _run(source, account, artifact_root):
    (
        contributor_set,
        decisions,
        portfolio_target,
        risk_policy,
        risk_target,
    ) = source
    return run_semantic_target_dry_run(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        strategy_decisions=decisions,
        risk_policy=risk_policy,
        account=account,
        policy=_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        artifact_root=artifact_root,
        evaluated_at=_now(),
    )


def _claim(source, account, artifact_root):
    contributor_set, _, portfolio_target, _, risk_target = source
    return claim_execution_plan(
        risk_target=risk_target,
        portfolio_target=portfolio_target,
        contributor_set=contributor_set,
        account=account,
        policy=_policy(),
        artifact_root=artifact_root,
        created_at=_now(),
    )


def _source(target_value: Decimal = Decimal("2")):
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
        max_age_seconds=3600,
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


def _policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _account(
    *,
    position_quantity: int = 0,
    open_order_ids: tuple[str, ...] = (),
) -> LiveAccountSnapshot:
    positions = (
        (
            Position(
                symbol="AAPL",
                quantity=position_quantity,
                average_price=100,
                last_price=100,
            ),
        )
        if position_quantity
        else ()
    )
    return LiveAccountSnapshot(
        id=f"snapshot-{position_quantity}-{len(open_order_ids)}",
        broker_name="local-dry-run",
        account_id="local-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        positions=positions,
        open_order_ids=open_order_ids,
        captured_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 6, 12, 12, tzinfo=UTC)
