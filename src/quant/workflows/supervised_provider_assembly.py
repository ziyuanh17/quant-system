"""Assemble supervised provider inputs from exact reviewed local artifacts."""

import json
import os
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    SupervisedHealthComponentObservation,
    SupervisedHealthSnapshot,
    SupervisedProviderAssemblyManifest,
    SupervisedProviderAssemblyRecord,
    SupervisedProviderComponentStatus,
    SupervisedProviderPolicy,
    SupervisedRequestEnvelope,
)
from quant.models.execution import TradingMode
from quant.models.targets import (
    ContributorSet,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
)
from quant.operations import FileLock
from quant.research.portfolio_targets import aggregate_strategy_targets
from quant.research.target_artifacts import (
    load_contributor_set,
    load_strategy_evaluation,
    load_strategy_target_decision,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)
from quant.workflows.supervised_provider_inputs import (
    load_supervised_health_snapshot,
    load_supervised_provider_policy,
    load_supervised_request_envelope,
    write_supervised_health_snapshot,
    write_supervised_request_envelope,
)

LOCAL_PROVIDER_ASSEMBLY_VERSION = "local_reviewed_artifacts_v1"
LOCAL_HEALTH_SOURCE_ID = "local-reviewed-artifacts-health"
LOCAL_REQUEST_SOURCE_ID = "local-reviewed-artifacts-request"
_ASSEMBLED_HEALTH_COMPONENTS = {
    "semantic-targets",
    "dry-run-account",
    "execution-inputs",
}


def assemble_local_supervised_provider_inputs(
    *,
    manifest: SupervisedProviderAssemblyManifest,
    output_root: Path,
) -> SupervisedProviderAssemblyRecord:
    """Build one immutable health snapshot and request envelope locally."""
    _require_safe_component(manifest.assembly_id, "assembly ID")
    digest = _model_sha256(manifest)
    assembly_root = output_root / "assemblies" / manifest.assembly_id
    record_path = assembly_root / "record.json"
    with FileLock(
        path=output_root / "locks" / f"{manifest.assembly_id}.lock",
        lock_name=f"supervised-provider-assembly:{manifest.assembly_id}",
        stale_after_seconds=300,
    ):
        _persist_or_verify_manifest(manifest, assembly_root)
        if record_path.exists():
            record = load_supervised_provider_assembly_record(record_path)
            if record.manifest_sha256 != digest:
                raise ValueError(
                    "provider assembly ID is bound to other inputs"
                )
            _verify_record_outputs(record)
            return record

        policy_path = Path(manifest.provider_policy_path)
        authorization_path = Path(manifest.authorization_path)
        contributor_set_path = Path(manifest.contributor_set_path)
        _require_hash(policy_path, manifest.provider_policy_sha256)
        _require_hash(authorization_path, manifest.authorization_sha256)
        _require_hash(contributor_set_path, manifest.contributor_set_sha256)
        policy = load_supervised_provider_policy(policy_path)
        authorization = load_autonomous_dry_run_authorization(
            authorization_path
        )
        contributor_set = load_contributor_set(contributor_set_path)
        decisions = tuple(
            load_strategy_target_decision(_verified_path(path, digest_value))
            for path, digest_value in zip(
                manifest.strategy_decision_paths,
                manifest.strategy_decision_sha256s,
                strict=True,
            )
        )
        evaluations = tuple(
            load_strategy_evaluation(_verified_path(path, digest_value))
            for path, digest_value in zip(
                manifest.strategy_evaluation_paths,
                manifest.strategy_evaluation_sha256s,
                strict=True,
            )
        )
        _validate_inputs(
            manifest,
            policy,
            authorization,
            contributor_set,
            decisions,
            evaluations,
        )

        evidence = (
            str(assembly_root / "manifest.json"),
            manifest.provider_policy_path,
            manifest.authorization_path,
            manifest.contributor_set_path,
            *manifest.strategy_decision_paths,
            *manifest.strategy_evaluation_paths,
            *manifest.evidence_refs,
        )
        snapshot_id = f"{manifest.assembly_id}-health"
        envelope_id = f"{manifest.assembly_id}-request"
        health = SupervisedHealthSnapshot(
            snapshot_id=snapshot_id,
            service_id=manifest.service_id,
            cycle_index=manifest.cycle_index,
            health_source_id=policy.health_source_id,
            health_source_version=policy.health_source_version,
            generated_at=manifest.generated_at,
            components=(
                _component("semantic-targets", manifest, evidence),
                _component("dry-run-account", manifest, evidence),
                _component("execution-inputs", manifest, evidence),
            ),
            evidence_refs=evidence,
        )
        request = AutonomousDryRunRequest(
            run_id=f"{manifest.assembly_id}-run",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            orchestration_id=f"{manifest.assembly_id}-orchestration",
            contributor_set=contributor_set,
            strategy_decisions=decisions,
            strategy_evaluations=evaluations,
            risk_policy=manifest.risk_policy,
            portfolio_target_id=manifest.portfolio_target_id,
            portfolio_target_revision=manifest.portfolio_target_revision,
            risk_target_id=manifest.risk_target_id,
            risk_target_revision=manifest.risk_target_revision,
            account=manifest.account,
            execution_policy=manifest.execution_policy,
            reference_price=manifest.reference_price,
            evaluated_at=manifest.generated_at,
            evidence_refs=evidence,
        )
        envelope = SupervisedRequestEnvelope(
            envelope_id=envelope_id,
            service_id=manifest.service_id,
            cycle_index=manifest.cycle_index,
            request_source_id=policy.request_source_id,
            request_source_version=policy.request_source_version,
            generated_at=manifest.generated_at,
            valid_until=manifest.valid_until,
            request=request,
            evidence_refs=evidence,
        )
        health_path = write_supervised_health_snapshot(
            health, output_root / "provider-inputs"
        )
        envelope_path = write_supervised_request_envelope(
            envelope, output_root / "provider-inputs"
        )
        record = SupervisedProviderAssemblyRecord(
            assembly_id=manifest.assembly_id,
            manifest_sha256=digest,
            service_id=manifest.service_id,
            cycle_index=manifest.cycle_index,
            health_snapshot_id=snapshot_id,
            request_envelope_id=envelope_id,
            health_snapshot_path=str(health_path),
            health_snapshot_sha256=_file_sha256(health_path),
            request_envelope_path=str(envelope_path),
            request_envelope_sha256=_file_sha256(envelope_path),
            assembled_at=manifest.generated_at,
            evidence_refs=evidence,
        )
        _write_model_exclusive(record_path, record)
        return record


def write_supervised_provider_assembly_manifest(
    manifest: SupervisedProviderAssemblyManifest, output_root: Path
) -> Path:
    """Write one immutable provider-assembly manifest."""
    _require_safe_component(manifest.assembly_id, "assembly ID")
    path = output_root / f"{manifest.assembly_id}.json"
    _write_model_exclusive(path, manifest)
    return path


def load_supervised_provider_assembly_manifest(
    path: Path,
) -> SupervisedProviderAssemblyManifest:
    """Load one provider-assembly manifest."""
    return SupervisedProviderAssemblyManifest.model_validate_json(
        path.read_text()
    )


def load_supervised_provider_assembly_record(
    path: Path,
) -> SupervisedProviderAssemblyRecord:
    """Load one durable provider-assembly result."""
    return SupervisedProviderAssemblyRecord.model_validate_json(
        path.read_text()
    )


def _validate_inputs(
    manifest: SupervisedProviderAssemblyManifest,
    policy: SupervisedProviderPolicy,
    authorization: AutonomousDryRunAuthorization,
    contributor_set: ContributorSet,
    decisions: tuple[StrategyTargetDecision, ...],
    evaluations: tuple[StrategyEvaluation, ...],
) -> None:
    issues: list[str] = []
    if policy.service_id != manifest.service_id:
        issues.append("provider policy references another service")
    if (
        policy.authorization_id != authorization.authorization_id
        or policy.authorization_revision != authorization.revision
    ):
        issues.append("provider policy references another authorization")
    if (
        policy.health_source_id != LOCAL_HEALTH_SOURCE_ID
        or policy.request_source_id != LOCAL_REQUEST_SOURCE_ID
        or policy.health_source_version != LOCAL_PROVIDER_ASSEMBLY_VERSION
        or policy.request_source_version != LOCAL_PROVIDER_ASSEMBLY_VERSION
    ):
        issues.append("provider policy does not authorize local assembly")
    if not set(policy.required_health_components).issubset(
        _ASSEMBLED_HEALTH_COMPONENTS
    ):
        issues.append("provider policy requires unsupported health components")
    if (
        manifest.generated_at < authorization.effective_at
        or manifest.generated_at >= authorization.valid_until
    ):
        issues.append("authorization is not active at assembly time")
    if manifest.valid_until > authorization.valid_until:
        issues.append("assembly validity exceeds authorization validity")
    if manifest.account.broker_environment != TradingMode.DRY_RUN.value:
        issues.append("assembly account is not marked dry_run")
    if (
        manifest.account.broker_name != authorization.broker_name
        or manifest.account.account_id != authorization.account_id
    ):
        issues.append("assembly account identity is not authorized")
    if manifest.account.captured_at > manifest.generated_at:
        issues.append("assembly account snapshot is future-dated")
    elif (
        manifest.generated_at - manifest.account.captured_at
    ).total_seconds() > policy.maximum_health_age_seconds:
        issues.append("assembly account snapshot is stale")
    if (
        contributor_set.contributor_set_id != authorization.contributor_set_id
        or contributor_set.revision != authorization.contributor_set_revision
        or contributor_set.symbol != authorization.symbol
    ):
        issues.append("contributor set is not authorized")
    expected = {
        (item.strategy_id, item.strategy_version)
        for item in contributor_set.expected_contributors
    }
    if expected != set(authorization.allowed_strategies):
        issues.append("contributor strategies are not authorized")
    decision_ids = {item.decision_id for item in decisions}
    if len(decision_ids) != len(decisions):
        issues.append("strategy decision identities must be unique")
    if {
        (item.strategy_id, item.strategy_version) for item in decisions
    } != expected:
        issues.append("strategy decisions do not exactly match contributors")
    if len({item.evaluation_id for item in evaluations}) != len(evaluations):
        issues.append("strategy evaluation identities must be unique")
    if {
        (item.strategy_id, item.strategy_version) for item in evaluations
    } != expected:
        issues.append("strategy evaluations do not exactly match contributors")
    for evaluation in evaluations:
        if evaluation.evaluated_at != manifest.generated_at:
            issues.append(
                "strategy evaluation time does not match assembly time"
            )
        if (
            evaluation.outcome == StrategyEvaluationOutcome.UNAVAILABLE
            or evaluation.effective_target_decision_id not in decision_ids
        ):
            issues.append(
                "strategy evaluation does not reference an available decision"
            )
            continue
        decision = next(
            item
            for item in decisions
            if item.decision_id == evaluation.effective_target_decision_id
        )
        if (
            evaluation.strategy_id != decision.strategy_id
            or evaluation.strategy_version != decision.strategy_version
            or evaluation.symbol != decision.symbol
        ):
            issues.append(
                "strategy evaluation identity does not match decision"
            )
    if any(manifest.valid_until > item.valid_until for item in decisions):
        issues.append("assembly validity exceeds strategy target validity")
    portfolio = aggregate_strategy_targets(
        portfolio_target_id=manifest.portfolio_target_id,
        revision=manifest.portfolio_target_revision,
        contributor_set=contributor_set,
        decisions=decisions,
        evaluated_at=manifest.generated_at,
    )
    if portfolio.aggregate_value is None:
        issues.append("strategy target artifacts do not aggregate actively")
    elif (
        abs(portfolio.aggregate_value)
        > authorization.max_absolute_target_shares
    ):
        issues.append("aggregate target exceeds authorization limit")
    elif (
        portfolio.aggregate_value < 0 and not authorization.allow_short_targets
    ):
        issues.append("short targets are not authorized")
    if manifest.risk_policy.max_absolute_target is None or (
        manifest.risk_policy.max_absolute_target
        > authorization.max_absolute_target_shares
    ):
        issues.append("risk policy exceeds authorization target limit")
    if issues:
        raise ValueError("; ".join(issues))


def _component(
    component_id: str,
    manifest: SupervisedProviderAssemblyManifest,
    evidence: tuple[str, ...],
) -> SupervisedHealthComponentObservation:
    return SupervisedHealthComponentObservation(
        component_id=component_id,
        status=SupervisedProviderComponentStatus.HEALTHY,
        observed_at=manifest.generated_at,
        valid_until=manifest.valid_until,
        reason=f"local reviewed {component_id} artifacts validated",
        evidence_refs=evidence,
    )


def _verified_path(path_value: str, digest: str) -> Path:
    path = Path(path_value)
    _require_hash(path, digest)
    return path


def _persist_or_verify_manifest(
    manifest: SupervisedProviderAssemblyManifest, assembly_root: Path
) -> None:
    path = assembly_root / "manifest.json"
    if path.exists():
        if load_supervised_provider_assembly_manifest(path) != manifest:
            raise ValueError("immutable provider assembly manifest conflicts")
        return
    _write_model_exclusive(path, manifest)


def _verify_record_outputs(record: SupervisedProviderAssemblyRecord) -> None:
    health_path = Path(record.health_snapshot_path)
    envelope_path = Path(record.request_envelope_path)
    for path in (health_path, envelope_path):
        if not path.is_file():
            raise ValueError(f"provider assembly output is missing: {path}")
    if (
        _file_sha256(health_path) != record.health_snapshot_sha256
        or _file_sha256(envelope_path) != record.request_envelope_sha256
    ):
        raise ValueError("provider assembly output hash does not match record")
    health = load_supervised_health_snapshot(health_path)
    envelope = load_supervised_request_envelope(envelope_path)
    if (
        health.snapshot_id != record.health_snapshot_id
        or envelope.envelope_id != record.request_envelope_id
        or health.service_id != record.service_id
        or envelope.service_id != record.service_id
        or health.cycle_index != record.cycle_index
        or envelope.cycle_index != record.cycle_index
    ):
        raise ValueError("provider assembly outputs do not match record")


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file():
        raise ValueError(f"provider assembly input is missing: {path}")
    if _file_sha256(path) != expected:
        raise ValueError(f"provider assembly input hash does not match: {path}")


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def _model_sha256(model: BaseModel) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return sha256(payload).hexdigest()


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_safe_component(value: str, label: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a safe path component")
