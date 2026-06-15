"""Test the bounded API-only supervised autonomous dry-run service."""

from contextlib import suppress
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
    SupervisedDryRunCycleOutcome,
    SupervisedDryRunHealthCheck,
    SupervisedDryRunHealthStatus,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
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
from quant.workflows import (
    load_supervised_dry_run_cycle_events,
    run_supervised_autonomous_dry_run_service,
)


def test_supervisor_completes_healthy_bounded_cycles(tmp_path) -> None:
    sleeps: list[float] = []
    record = run_supervised_autonomous_dry_run_service(
        policy=_policy(maximum_cycles=2, interval_seconds=60),
        authorization=_authorization(),
        request_provider=lambda cycle, now: _request(f"run-{cycle}", now),
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now(), _now() + timedelta(minutes=1)),
        sleeper=sleeps.append,
    )

    assert record.status == SupervisedDryRunServiceStatus.COMPLETED
    assert record.completed_cycles == 2
    assert record.run_ids == ("run-1", "run-2")
    assert sleeps == [60]
    assert len(tuple((tmp_path / "services").rglob("events/*.json"))) == 2
    assert not (tmp_path / "orders").exists()
    assert not (tmp_path / "fills").exists()
    assert not (tmp_path / "semantic-paper").exists()


def test_supervisor_stops_before_request_when_health_is_degraded(
    tmp_path,
) -> None:
    requested: list[int] = []

    def request_provider(cycle: int, now: datetime) -> AutonomousDryRunRequest:
        requested.append(cycle)
        return _request(f"run-{cycle}", now)

    record = run_supervised_autonomous_dry_run_service(
        policy=_policy(),
        authorization=_authorization(),
        request_provider=request_provider,
        health_provider=lambda cycle, now: SupervisedDryRunHealthCheck(
            check_id=f"health-{cycle}",
            service_id="supervisor-1",
            cycle_index=cycle,
            status=SupervisedDryRunHealthStatus.DEGRADED,
            checked_at=now,
            reasons=("input freshness uncertain",),
        ),
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    events = load_supervised_dry_run_cycle_events(
        tmp_path / "services" / "supervisor-1",
        "supervisor-1",
        record.policy_sha256,
    )
    assert record.status == SupervisedDryRunServiceStatus.STOPPED
    assert record.completed_cycles == 0
    assert events[-1].outcome == SupervisedDryRunCycleOutcome.HEALTH_STOP
    assert requested == []
    assert not (tmp_path / "autonomous").exists()


def test_supervisor_honors_explicit_shutdown_before_health(tmp_path) -> None:
    health_checks: list[int] = []

    def health(cycle: int, now: datetime) -> SupervisedDryRunHealthCheck:
        health_checks.append(cycle)
        return _healthy(cycle, now)

    record = run_supervised_autonomous_dry_run_service(
        policy=_policy(),
        authorization=_authorization(),
        request_provider=lambda cycle, now: _request(f"run-{cycle}", now),
        health_provider=health,
        shutdown_requested=lambda: True,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.STOPPED
    assert "shutdown" in record.reason
    assert health_checks == []
    assert not (tmp_path / "autonomous").exists()


def test_supervisor_stops_after_blocked_autonomous_run(tmp_path) -> None:
    requested: list[int] = []

    def request_provider(cycle: int, now: datetime) -> AutonomousDryRunRequest:
        requested.append(cycle)
        return _request(
            f"run-{cycle}",
            now,
            open_order_ids=("working-order-1",) if cycle == 1 else (),
        )

    record = run_supervised_autonomous_dry_run_service(
        policy=_policy(),
        authorization=_authorization(),
        request_provider=request_provider,
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.STOPPED
    assert record.completed_cycles == 0
    assert requested == [1]
    assert len(record.run_ids) == 1


def test_supervisor_restart_continues_after_last_durable_cycle(
    tmp_path,
) -> None:
    policy = _policy(maximum_cycles=2, interval_seconds=60)
    authorization = _authorization()
    first_clock = _Clock(_now(), _now())

    def crash_after_event(_: float) -> None:
        raise KeyboardInterrupt

    with suppress(KeyboardInterrupt):
        run_supervised_autonomous_dry_run_service(
            policy=policy,
            authorization=authorization,
            request_provider=lambda cycle, now: _request(f"run-{cycle}", now),
            health_provider=_healthy,
            shutdown_requested=lambda: False,
            output_root=tmp_path,
            clock=first_clock,
            sleeper=crash_after_event,
        )

    record = run_supervised_autonomous_dry_run_service(
        policy=policy,
        authorization=authorization,
        request_provider=lambda cycle, now: _request(f"run-{cycle}", now),
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now() + timedelta(minutes=1)),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.COMPLETED
    assert record.run_ids == ("run-1", "run-2")
    assert len(tuple((tmp_path / "autonomous" / "runs").glob("*.json"))) == 2


def test_supervisor_restart_reuses_health_written_before_interruption(
    tmp_path,
) -> None:
    policy = _policy(maximum_cycles=1)
    authorization = _authorization()

    def interrupt_after_health(_: int, __: datetime) -> AutonomousDryRunRequest:
        raise KeyboardInterrupt

    with suppress(KeyboardInterrupt):
        run_supervised_autonomous_dry_run_service(
            policy=policy,
            authorization=authorization,
            request_provider=interrupt_after_health,
            health_provider=_healthy,
            shutdown_requested=lambda: False,
            output_root=tmp_path,
            clock=_Clock(_now(), _now()),
            sleeper=lambda _: None,
        )

    record = run_supervised_autonomous_dry_run_service(
        policy=policy,
        authorization=authorization,
        request_provider=lambda cycle, now: _request(f"run-{cycle}", now),
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    health_root = tmp_path / "services" / "supervisor-1" / "health-checks"
    assert record.status == SupervisedDryRunServiceStatus.COMPLETED
    assert record.run_ids == ("run-1",)
    assert len(tuple(health_root.glob("*.json"))) == 1


def test_supervisor_provider_error_becomes_durable_stop(tmp_path) -> None:
    def fail(_: int, __: datetime) -> AutonomousDryRunRequest:
        raise RuntimeError("request source unavailable")

    record = run_supervised_autonomous_dry_run_service(
        policy=_policy(),
        authorization=_authorization(),
        request_provider=fail,
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.STOPPED
    assert "request source unavailable" in record.reason
    assert record.completed_cycles == 0


def test_supervisor_stops_before_run_when_runtime_bound_is_reached(
    tmp_path,
) -> None:
    requested: list[int] = []

    def request_provider(cycle: int, now: datetime) -> AutonomousDryRunRequest:
        requested.append(cycle)
        return _request(f"run-{cycle}", now)

    record = run_supervised_autonomous_dry_run_service(
        policy=_policy().model_copy(update={"maximum_runtime_seconds": 30}),
        authorization=_authorization(),
        request_provider=request_provider,
        health_provider=_healthy,
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now() + timedelta(seconds=30)),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.STOPPED
    assert "maximum runtime" in record.reason
    assert requested == []
    assert not (tmp_path / "autonomous").exists()


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def _healthy(cycle: int, now: datetime) -> SupervisedDryRunHealthCheck:
    return SupervisedDryRunHealthCheck(
        check_id=f"health-{cycle}",
        service_id="supervisor-1",
        cycle_index=cycle,
        status=SupervisedDryRunHealthStatus.HEALTHY,
        checked_at=now,
    )


def _policy(
    *,
    maximum_cycles: int = 3,
    interval_seconds: float = 0,
) -> SupervisedDryRunServicePolicy:
    return SupervisedDryRunServicePolicy(
        service_id="supervisor-1",
        policy_version="bounded_supervised_dry_run_v1",
        authorization_id="supervisor-authorization",
        authorization_revision=1,
        maximum_cycles=maximum_cycles,
        interval_seconds=interval_seconds,
        maximum_runtime_seconds=3600,
        created_at=_now(),
        evidence_refs=("design:supervised-dry-run",),
    )


def _authorization() -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id="supervisor-authorization",
        revision=1,
        symbol="AAPL",
        contributor_set_id="supervisor-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="supervisor-dry-run",
        account_id="supervisor-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=10,
        minimum_interval_seconds=0,
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=_now() + timedelta(hours=2),
        issued_by="test-deployment-review",
        reason="supervised autonomous dry-run test",
        evidence_refs=("review:test",),
    )


def _request(
    run_id: str,
    evaluated_at: datetime,
    *,
    open_order_ids: tuple[str, ...] = (),
) -> AutonomousDryRunRequest:
    decision = StrategyTargetDecision(
        decision_id=f"{run_id}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{run_id}-input",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="supervised test target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{run_id}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="supervised test evaluation",
    )
    return AutonomousDryRunRequest(
        run_id=run_id,
        authorization_id="supervisor-authorization",
        authorization_revision=1,
        orchestration_id=f"{run_id}-orchestration",
        contributor_set=ContributorSet(
            contributor_set_id="supervisor-contributors",
            revision=1,
            symbol="AAPL",
            unit=TargetUnit.SHARES,
            expected_contributors=(
                ContributorSpec(strategy_id="momentum", strategy_version="2"),
            ),
            max_age_seconds=3600,
            portfolio_policy_version="sum_active_targets_v1",
            reason="supervised test ownership",
        ),
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
        account=LiveAccountSnapshot(
            id=f"{run_id}-account",
            broker_name="supervisor-dry-run",
            account_id="supervisor-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            open_order_ids=open_order_ids,
            captured_at=evaluated_at,
        ),
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


def _now() -> datetime:
    return datetime(2026, 6, 15, 20, tzinfo=UTC)
