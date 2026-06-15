"""Test bounded autonomous semantic-target dry-run authorization."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
)
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
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
from quant.workflows import run_authorized_autonomous_dry_run


def test_authorized_autonomous_dry_runs_repeat_without_human_order_review(
    tmp_path,
) -> None:
    authorization = _authorization()

    first = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-1", _now()),
        output_root=tmp_path,
        run_at=_now(),
    )
    second = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-2", _now() + timedelta(minutes=5)),
        output_root=tmp_path,
        run_at=_now() + timedelta(minutes=5),
    )

    assert first.status == AutonomousDryRunStatus.SUCCEEDED
    assert second.status == AutonomousDryRunStatus.SUCCEEDED
    assert len(tuple((tmp_path / "runs").glob("*.json"))) == 2
    assert len(tuple((tmp_path / "authorizations").rglob("*.json"))) == 1
    assert not (tmp_path / "orders").exists()
    assert not (tmp_path / "fills").exists()


def test_autonomous_run_is_restart_safe(tmp_path) -> None:
    authorization = _authorization()
    request = _request("run-1", _now())

    first = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=tmp_path,
        run_at=_now(),
    )
    second = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=tmp_path,
        run_at=_now(),
    )

    assert first == second
    assert len(tuple((tmp_path / "runs").glob("*.json"))) == 1
    assert len(
        tuple((tmp_path / "workflows" / "orchestrations").glob("*.json"))
    ) == 1


def test_blocked_run_halts_later_runs(tmp_path) -> None:
    authorization = _authorization()
    blocked_request = _request("run-blocked", _now()).model_copy(
        update={
            "account": _account(open_order_ids=("working-order-1",)),
        }
    )

    blocked = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=blocked_request,
        output_root=tmp_path,
        run_at=_now(),
    )
    later = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-later", _now() + timedelta(minutes=5)),
        output_root=tmp_path,
        run_at=_now() + timedelta(minutes=5),
    )

    assert blocked.status == AutonomousDryRunStatus.BLOCKED
    assert later.status == AutonomousDryRunStatus.BLOCKED
    assert "prior autonomous run is blocked" in later.reason
    assert later.orchestration_id is None


def test_authorization_blocks_expiry_interval_and_run_limit(tmp_path) -> None:
    authorization = _authorization(maximum_runs=1)
    first = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-1", _now()),
        output_root=tmp_path,
        run_at=_now(),
    )
    too_soon = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-2", _now() + timedelta(seconds=30)),
        output_root=tmp_path,
        run_at=_now() + timedelta(seconds=30),
    )

    assert first.status == AutonomousDryRunStatus.SUCCEEDED
    assert too_soon.status == AutonomousDryRunStatus.BLOCKED
    assert "maximum run count reached" in too_soon.reason
    assert "minimum interval" in too_soon.reason

    other_root = tmp_path / "expired"
    expired = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-expired", _now() + timedelta(hours=2)),
        output_root=other_root,
        run_at=_now() + timedelta(hours=2),
    )
    assert expired.status == AutonomousDryRunStatus.BLOCKED
    assert "authorization is expired" in expired.reason


def test_authorization_blocks_target_above_deployment_limit(tmp_path) -> None:
    authorization = _authorization(max_absolute_target_shares=Decimal("2"))
    request = _request("run-large", _now(), target=Decimal("3"))

    record = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=tmp_path,
        run_at=_now(),
    )

    assert record.status == AutonomousDryRunStatus.BLOCKED
    assert "aggregate target exceeds authorization limit" in record.reason
    assert not (tmp_path / "workflows").exists()


def test_workflow_error_is_durable_and_halts_later_runs(tmp_path) -> None:
    authorization = _authorization()
    invalid = _request("run-invalid", _now()).model_copy(
        update={"strategy_evaluations": ()}
    )

    failed = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=invalid,
        output_root=tmp_path,
        run_at=_now(),
    )
    later = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=_request("run-later", _now() + timedelta(minutes=5)),
        output_root=tmp_path,
        run_at=_now() + timedelta(minutes=5),
    )

    assert failed.status == AutonomousDryRunStatus.BLOCKED
    assert "dry-run workflow failed" in failed.reason
    assert later.status == AutonomousDryRunStatus.BLOCKED
    assert "prior autonomous run is blocked" in later.reason


def test_short_target_requires_explicit_authorization(tmp_path) -> None:
    record = run_authorized_autonomous_dry_run(
        authorization=_authorization(),
        request=_request("run-short", _now(), target=Decimal("-2")),
        output_root=tmp_path,
        run_at=_now(),
    )

    assert record.status == AutonomousDryRunStatus.BLOCKED
    assert "short targets are not authorized" in record.reason


def _authorization(
    *,
    maximum_runs: int = 5,
    max_absolute_target_shares: Decimal = Decimal("10"),
) -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id="autonomous-dry-aapl",
        revision=1,
        symbol="AAPL",
        contributor_set_id="aapl-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="local-dry-run-snapshot",
        account_id="local-dry-run-account",
        max_absolute_target_shares=max_absolute_target_shares,
        maximum_runs=maximum_runs,
        minimum_interval_seconds=60,
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=_now() + timedelta(hours=1),
        issued_by="test-deployment-review",
        reason="bounded autonomous dry-run test",
        evidence_refs=("review:test",),
    )


def _request(
    run_id: str,
    evaluated_at: datetime,
    *,
    target: Decimal = Decimal("2"),
) -> AutonomousDryRunRequest:
    decision = StrategyTargetDecision(
        decision_id=f"{run_id}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target,
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{run_id}-input",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(minutes=30),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="autonomous dry-run test target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{run_id}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="autonomous dry-run test evaluation",
    )
    return AutonomousDryRunRequest(
        run_id=run_id,
        authorization_id="autonomous-dry-aapl",
        authorization_revision=1,
        orchestration_id=f"{run_id}-orchestration",
        contributor_set=_contributor_set(),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id=f"{run_id}-portfolio",
        portfolio_target_revision=1,
        risk_target_id=f"{run_id}-risk",
        risk_target_revision=1,
        account=_account(),
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        evaluated_at=evaluated_at,
    )


def _contributor_set() -> ContributorSet:
    return ContributorSet(
        contributor_set_id="aapl-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="autonomous dry-run test ownership",
    )


def _account(
    *, open_order_ids: tuple[str, ...] = ()
) -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        id=f"account-{len(open_order_ids)}",
        broker_name="local-dry-run-snapshot",
        account_id="local-dry-run-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        open_order_ids=open_order_ids,
        captured_at=_now(),
    )


def _now() -> datetime:
    return datetime(2026, 6, 15, 16, tzinfo=UTC)
