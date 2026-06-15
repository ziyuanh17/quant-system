"""Test durable production-input contracts for supervised dry-runs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    SupervisedDryRunHealthStatus,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
    SupervisedHealthComponentObservation,
    SupervisedHealthSnapshot,
    SupervisedProviderComponentStatus,
    SupervisedProviderPolicy,
    SupervisedRequestEnvelope,
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
    evaluate_supervised_health_snapshot,
    load_supervised_health_snapshot,
    load_supervised_provider_policy,
    load_supervised_request_envelope,
    resolve_supervised_request_envelope,
    run_supervised_autonomous_dry_run_service,
    write_supervised_health_snapshot,
    write_supervised_provider_policy,
    write_supervised_request_envelope,
)


def test_complete_fresh_health_snapshot_is_healthy() -> None:
    check = evaluate_supervised_health_snapshot(
        policy=_provider_policy(),
        snapshot=_health_snapshot(),
        cycle_index=1,
        checked_at=_now(),
    )

    assert check.status == SupervisedDryRunHealthStatus.HEALTHY
    assert not check.reasons


@pytest.mark.parametrize(
    (
        "components",
        "component_status",
        "age_minutes",
        "expected_status",
        "reason",
    ),
    [
        (
            ("targets",),
            SupervisedProviderComponentStatus.HEALTHY,
            0,
            SupervisedDryRunHealthStatus.FAILED,
            "required health component is missing",
        ),
        (
            ("targets", "account"),
            SupervisedProviderComponentStatus.DEGRADED,
            0,
            SupervisedDryRunHealthStatus.DEGRADED,
            "health component degraded",
        ),
        (
            ("targets", "account"),
            SupervisedProviderComponentStatus.FAILED,
            0,
            SupervisedDryRunHealthStatus.FAILED,
            "health component failed",
        ),
        (
            ("targets", "account"),
            SupervisedProviderComponentStatus.HEALTHY,
            6,
            SupervisedDryRunHealthStatus.DEGRADED,
            "health snapshot is stale",
        ),
    ],
)
def test_health_snapshot_fails_closed(
    components: tuple[str, ...],
    component_status: SupervisedProviderComponentStatus,
    age_minutes: int,
    expected_status: SupervisedDryRunHealthStatus,
    reason: str,
) -> None:
    snapshot = _health_snapshot(
        components=components,
        component_status=component_status,
        generated_at=_now() - timedelta(minutes=age_minutes),
    )
    check = evaluate_supervised_health_snapshot(
        policy=_provider_policy(),
        snapshot=snapshot,
        cycle_index=1,
        checked_at=_now(),
    )

    assert check.status == expected_status
    assert any(reason in item for item in check.reasons)


def test_unlisted_failed_health_component_still_fails_closed() -> None:
    snapshot = _health_snapshot().model_copy(
        update={
            "components": (
                *_health_snapshot().components,
                SupervisedHealthComponentObservation(
                    component_id="unexpected-source",
                    status=SupervisedProviderComponentStatus.FAILED,
                    observed_at=_now(),
                    valid_until=_now() + timedelta(minutes=5),
                    reason="unexpected component failed",
                ),
            )
        }
    )

    check = evaluate_supervised_health_snapshot(
        policy=_provider_policy(),
        snapshot=snapshot,
        cycle_index=1,
        checked_at=_now(),
    )

    assert check.status == SupervisedDryRunHealthStatus.FAILED
    assert any("unexpected-source" in item for item in check.reasons)


def test_fresh_request_envelope_resolves_exact_request() -> None:
    request = _request(_now())
    envelope = _envelope(request)

    resolved = resolve_supervised_request_envelope(
        policy=_provider_policy(),
        authorization=_authorization(),
        envelope=envelope,
        cycle_index=1,
        requested_at=_now(),
    )

    assert resolved == request


@pytest.mark.parametrize(
    ("case", "reason"),
    [
        ("stale", "stale"),
        ("expired", "expired"),
        ("wrong_source", "source identity"),
        ("wrong_cycle", "another cycle"),
    ],
)
def test_request_envelope_rejects_invalid_freshness_or_identity(
    case: str, reason: str
) -> None:
    envelope = {
        "stale": _envelope(
            _request(_now()),
            generated_at=_now() - timedelta(minutes=6),
        ),
        "expired": _envelope(
            _request(_now()),
            generated_at=_now() - timedelta(minutes=2),
            valid_until=_now() - timedelta(minutes=1),
        ),
        "wrong_source": _envelope(
            _request(_now()), request_source_version="wrong"
        ),
        "wrong_cycle": _envelope(_request(_now()), cycle_index=2),
    }[case]
    with pytest.raises(ValueError, match=reason):
        resolve_supervised_request_envelope(
            policy=_provider_policy(),
            authorization=_authorization(),
            envelope=envelope,
            cycle_index=1,
            requested_at=_now(),
        )


def test_provider_artifacts_are_immutable_and_readable(tmp_path) -> None:
    policy = _provider_policy()
    snapshot = _health_snapshot()
    envelope = _envelope(_request(_now()))

    policy_path = write_supervised_provider_policy(policy, tmp_path)
    snapshot_path = write_supervised_health_snapshot(snapshot, tmp_path)
    envelope_path = write_supervised_request_envelope(envelope, tmp_path)

    assert load_supervised_provider_policy(policy_path) == policy
    assert load_supervised_health_snapshot(snapshot_path) == snapshot
    assert load_supervised_request_envelope(envelope_path) == envelope
    with pytest.raises(FileExistsError):
        write_supervised_health_snapshot(snapshot, tmp_path)


def test_provider_adapters_feed_supervisor_without_operational_output(
    tmp_path,
) -> None:
    provider_policy = _provider_policy()
    authorization = _authorization()
    snapshot = _health_snapshot()
    envelope = _envelope(_request(_now()))

    record = run_supervised_autonomous_dry_run_service(
        policy=SupervisedDryRunServicePolicy(
            service_id="provider-service",
            policy_version="bounded_supervised_dry_run_v1",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            maximum_cycles=1,
            interval_seconds=0,
            maximum_runtime_seconds=60,
            created_at=_now(),
        ),
        authorization=authorization,
        health_provider=lambda cycle, now: evaluate_supervised_health_snapshot(
            policy=provider_policy,
            snapshot=snapshot,
            cycle_index=cycle,
            checked_at=now,
        ),
        request_provider=lambda cycle, now: resolve_supervised_request_envelope(
            policy=provider_policy,
            authorization=authorization,
            envelope=envelope,
            cycle_index=cycle,
            requested_at=now,
        ),
        shutdown_requested=lambda: False,
        output_root=tmp_path,
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    assert record.status == SupervisedDryRunServiceStatus.COMPLETED
    assert not (tmp_path / "orders").exists()
    assert not (tmp_path / "fills").exists()
    assert not (tmp_path / "semantic-paper").exists()


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def _provider_policy() -> SupervisedProviderPolicy:
    return SupervisedProviderPolicy(
        provider_policy_version="supervised_provider_inputs_v1",
        service_id="provider-service",
        authorization_id="provider-authorization",
        authorization_revision=1,
        health_source_id="local-health-builder",
        health_source_version="1",
        request_source_id="local-target-builder",
        request_source_version="1",
        required_health_components=("targets", "account"),
        maximum_health_age_seconds=300,
        maximum_request_age_seconds=300,
        evidence_refs=("provider-policy:test",),
    )


def _health_snapshot(
    *,
    components: tuple[str, ...] = ("targets", "account"),
    component_status: SupervisedProviderComponentStatus = (
        SupervisedProviderComponentStatus.HEALTHY
    ),
    generated_at: datetime | None = None,
) -> SupervisedHealthSnapshot:
    generated = generated_at or _now()
    return SupervisedHealthSnapshot(
        snapshot_id="health-snapshot-1",
        service_id="provider-service",
        cycle_index=1,
        health_source_id="local-health-builder",
        health_source_version="1",
        generated_at=generated,
        components=tuple(
            SupervisedHealthComponentObservation(
                component_id=component,
                status=component_status,
                observed_at=generated,
                valid_until=generated + timedelta(hours=1),
                reason="synthetic provider health",
            )
            for component in components
        ),
    )


def _envelope(
    request: AutonomousDryRunRequest,
    *,
    generated_at: datetime | None = None,
    valid_until: datetime | None = None,
    request_source_version: str = "1",
    cycle_index: int = 1,
) -> SupervisedRequestEnvelope:
    generated = generated_at or _now()
    return SupervisedRequestEnvelope(
        envelope_id="request-envelope-1",
        service_id="provider-service",
        cycle_index=cycle_index,
        request_source_id="local-target-builder",
        request_source_version=request_source_version,
        generated_at=generated,
        valid_until=valid_until or generated + timedelta(minutes=10),
        request=request,
    )


def _authorization() -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id="provider-authorization",
        revision=1,
        symbol="AAPL",
        contributor_set_id="provider-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="provider-dry-run",
        account_id="provider-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=2,
        minimum_interval_seconds=0,
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=_now() + timedelta(hours=1),
        issued_by="test",
        reason="provider contract test",
        evidence_refs=("review:test",),
    )


def _request(evaluated_at: datetime) -> AutonomousDryRunRequest:
    decision = StrategyTargetDecision(
        decision_id="provider-decision-1",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id="provider-input-1",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="provider test target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id="provider-evaluation-1",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="provider test evaluation",
    )
    return AutonomousDryRunRequest(
        run_id="provider-run-1",
        authorization_id="provider-authorization",
        authorization_revision=1,
        orchestration_id="provider-orchestration-1",
        contributor_set=ContributorSet(
            contributor_set_id="provider-contributors",
            revision=1,
            symbol="AAPL",
            unit=TargetUnit.SHARES,
            expected_contributors=(
                ContributorSpec(strategy_id="momentum", strategy_version="2"),
            ),
            max_age_seconds=3600,
            portfolio_policy_version="sum_active_targets_v1",
            reason="provider test ownership",
        ),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id="provider-portfolio-1",
        portfolio_target_revision=1,
        risk_target_id="provider-risk-1",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id="provider-account-snapshot-1",
            broker_name="provider-dry-run",
            account_id="provider-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
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
    return datetime(2026, 6, 15, 23, tzinfo=UTC)
