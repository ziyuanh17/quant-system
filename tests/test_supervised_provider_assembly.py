"""Test local no-network assembly of supervised provider inputs."""

from datetime import UTC, datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

import pytest

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    SupervisedDryRunHealthStatus,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
    SupervisedProviderAssemblyManifest,
    SupervisedProviderPolicy,
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
from quant.research import (
    write_contributor_set,
    write_strategy_evaluation,
    write_strategy_target_decision,
)
from quant.workflows import (
    LOCAL_HEALTH_SOURCE_ID,
    LOCAL_PROVIDER_ASSEMBLY_VERSION,
    LOCAL_REQUEST_SOURCE_ID,
    assemble_local_supervised_provider_inputs,
    evaluate_supervised_health_snapshot,
    load_supervised_health_snapshot,
    load_supervised_request_envelope,
    resolve_supervised_request_envelope,
    run_supervised_autonomous_dry_run_service,
    write_autonomous_dry_run_authorization,
    write_supervised_provider_policy,
)


def test_local_assembly_builds_valid_provider_inputs(tmp_path) -> None:
    manifest, authorization = _manifest(tmp_path)
    output_root = tmp_path / "output"

    record = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=output_root
    )
    health = load_supervised_health_snapshot(Path(record.health_snapshot_path))
    envelope = load_supervised_request_envelope(
        Path(record.request_envelope_path)
    )
    check = evaluate_supervised_health_snapshot(
        policy=_policy(),
        snapshot=health,
        cycle_index=1,
        checked_at=_now(),
    )
    request = resolve_supervised_request_envelope(
        policy=_policy(),
        authorization=authorization,
        envelope=envelope,
        cycle_index=1,
        requested_at=_now(),
    )

    assert check.status == SupervisedDryRunHealthStatus.HEALTHY
    assert request.run_id == "assembly-1-run"
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()
    assert not (output_root / "semantic-paper").exists()


def test_local_assembly_is_restart_safe(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)

    first = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=tmp_path / "output"
    )
    second = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=tmp_path / "output"
    )

    assert second == first


def test_local_assembly_rejects_changed_reviewed_artifact(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)
    path = Path(manifest.strategy_decision_paths[0])
    path.write_text(path.read_text().replace('"2"', '"3"', 1))

    with pytest.raises(ValueError, match="hash does not match"):
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=tmp_path / "output"
        )


def test_local_assembly_restart_detects_changed_output(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)
    output_root = tmp_path / "output"
    record = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=output_root
    )
    path = Path(record.health_snapshot_path)
    path.write_text(path.read_text().replace('"healthy"', '"failed"', 1))

    with pytest.raises(ValueError, match="output hash does not match"):
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=output_root
        )


def test_local_assembly_rejects_stale_target(tmp_path) -> None:
    manifest, _ = _manifest(
        tmp_path, decision_generated_at=_now() - timedelta(minutes=6)
    )

    with pytest.raises(ValueError, match="do not aggregate actively"):
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=tmp_path / "output"
        )


def test_local_assembly_rejects_stale_account_snapshot(tmp_path) -> None:
    manifest, _ = _manifest(
        tmp_path, account_captured_at=_now() - timedelta(minutes=6)
    )

    with pytest.raises(ValueError, match="account snapshot is stale"):
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=tmp_path / "output"
        )


def test_local_assembly_rejects_validity_beyond_target(tmp_path) -> None:
    manifest, _ = _manifest(tmp_path)
    manifest = manifest.model_copy(
        update={"valid_until": _now() + timedelta(minutes=10)}
    )

    with pytest.raises(ValueError, match="exceeds strategy target validity"):
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=tmp_path / "output"
        )


def test_local_assembly_outputs_feed_one_supervised_cycle(tmp_path) -> None:
    manifest, authorization = _manifest(tmp_path)
    output_root = tmp_path / "output"
    record = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=output_root
    )
    health = load_supervised_health_snapshot(Path(record.health_snapshot_path))
    envelope = load_supervised_request_envelope(
        Path(record.request_envelope_path)
    )

    service = run_supervised_autonomous_dry_run_service(
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
            policy=_policy(),
            snapshot=health,
            cycle_index=cycle,
            checked_at=now,
        ),
        request_provider=lambda cycle, now: resolve_supervised_request_envelope(
            policy=_policy(),
            authorization=authorization,
            envelope=envelope,
            cycle_index=cycle,
            requested_at=now,
        ),
        shutdown_requested=lambda: False,
        output_root=tmp_path / "service",
        clock=_Clock(_now(), _now()),
        sleeper=lambda _: None,
    )

    assert service.status == SupervisedDryRunServiceStatus.COMPLETED
    assert not (tmp_path / "service" / "orders").exists()
    assert not (tmp_path / "service" / "fills").exists()


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)


def _manifest(
    root: Path,
    *,
    decision_generated_at: datetime | None = None,
    account_captured_at: datetime | None = None,
) -> tuple[SupervisedProviderAssemblyManifest, AutonomousDryRunAuthorization]:
    inputs = root / "inputs"
    authorization = _authorization()
    policy_path = write_supervised_provider_policy(_policy(), inputs)
    authorization_path = write_autonomous_dry_run_authorization(
        authorization, inputs / "authorizations"
    )
    contributor_path = write_contributor_set(
        _contributor_set(), inputs / "contributor-sets"
    )
    decision = _decision(decision_generated_at=decision_generated_at)
    decision_path = write_strategy_target_decision(
        decision, inputs / "strategy-targets"
    )
    evaluation_path = write_strategy_evaluation(
        _evaluation(decision), inputs / "strategy-evaluations"
    )
    manifest = SupervisedProviderAssemblyManifest(
        assembly_id="assembly-1",
        service_id="provider-service",
        cycle_index=1,
        provider_policy_path=str(policy_path),
        provider_policy_sha256=_sha256(policy_path),
        authorization_path=str(authorization_path),
        authorization_sha256=_sha256(authorization_path),
        contributor_set_path=str(contributor_path),
        contributor_set_sha256=_sha256(contributor_path),
        strategy_decision_paths=(str(decision_path),),
        strategy_decision_sha256s=(_sha256(decision_path),),
        strategy_evaluation_paths=(str(evaluation_path),),
        strategy_evaluation_sha256s=(_sha256(evaluation_path),),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id="assembly-portfolio-1",
        portfolio_target_revision=1,
        risk_target_id="assembly-risk-1",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id="assembly-account-snapshot-1",
            broker_name="local-provider-dry-run",
            account_id="local-provider-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            captured_at=account_captured_at or _now(),
        ),
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        generated_at=_now(),
        valid_until=_now() + timedelta(minutes=5),
        evidence_refs=("reviewed:local-provider-assembly",),
    )
    return manifest, authorization


def _policy() -> SupervisedProviderPolicy:
    return SupervisedProviderPolicy(
        provider_policy_version="supervised_provider_inputs_v1",
        service_id="provider-service",
        authorization_id="provider-authorization",
        authorization_revision=1,
        health_source_id=LOCAL_HEALTH_SOURCE_ID,
        health_source_version=LOCAL_PROVIDER_ASSEMBLY_VERSION,
        request_source_id=LOCAL_REQUEST_SOURCE_ID,
        request_source_version=LOCAL_PROVIDER_ASSEMBLY_VERSION,
        required_health_components=(
            "semantic-targets",
            "dry-run-account",
            "execution-inputs",
        ),
        maximum_health_age_seconds=300,
        maximum_request_age_seconds=300,
        evidence_refs=("reviewed:provider-policy",),
    )


def _authorization() -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id="provider-authorization",
        revision=1,
        symbol="AAPL",
        contributor_set_id="provider-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="local-provider-dry-run",
        account_id="local-provider-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=2,
        minimum_interval_seconds=0,
        issued_at=_now() - timedelta(minutes=1),
        effective_at=_now() - timedelta(seconds=1),
        valid_until=_now() + timedelta(hours=1),
        issued_by="test-review",
        reason="local provider assembly test",
        evidence_refs=("review:test",),
    )


def _contributor_set() -> ContributorSet:
    return ContributorSet(
        contributor_set_id="provider-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=300,
        portfolio_policy_version="sum_active_targets_v1",
        reason="local provider assembly ownership",
    )


def _decision(
    *, decision_generated_at: datetime | None = None
) -> StrategyTargetDecision:
    generated_at = decision_generated_at or _now()
    return StrategyTargetDecision(
        decision_id="assembly-decision-1",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id="assembly-input-1",
        generated_at=generated_at,
        effective_at=generated_at,
        valid_until=_now() + timedelta(minutes=5),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="local provider assembly target",
    )


def _evaluation(decision: StrategyTargetDecision) -> StrategyEvaluation:
    return StrategyEvaluation(
        evaluation_id="assembly-evaluation-1",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=_now(),
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="local provider assembly evaluation",
    )


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _now() -> datetime:
    return datetime(2026, 6, 16, 0, tzinfo=UTC)
