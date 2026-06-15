"""Validate durable health and fresh-request inputs for supervised dry-runs."""

import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRequest,
    SupervisedDryRunHealthCheck,
    SupervisedDryRunHealthStatus,
    SupervisedHealthSnapshot,
    SupervisedProviderComponentStatus,
    SupervisedProviderPolicy,
    SupervisedRequestEnvelope,
)


def evaluate_supervised_health_snapshot(
    *,
    policy: SupervisedProviderPolicy,
    snapshot: SupervisedHealthSnapshot,
    cycle_index: int,
    checked_at: datetime,
) -> SupervisedDryRunHealthCheck:
    """Convert a provider snapshot into a fail-closed health check."""
    _require_aware(checked_at, "health evaluation time")
    issues: list[str] = []
    failed = False
    if snapshot.service_id != policy.service_id:
        issues.append("health snapshot references another service")
        failed = True
    if snapshot.cycle_index != cycle_index:
        issues.append("health snapshot references another cycle")
        failed = True
    if (
        snapshot.health_source_id != policy.health_source_id
        or snapshot.health_source_version != policy.health_source_version
    ):
        issues.append("health snapshot source identity is not allowed")
        failed = True
    if snapshot.generated_at > checked_at:
        issues.append("health snapshot is future-dated")
        failed = True
    elif (
        checked_at - snapshot.generated_at
    ).total_seconds() > policy.maximum_health_age_seconds:
        issues.append("health snapshot is stale")

    components = {item.component_id: item for item in snapshot.components}
    for component_id in policy.required_health_components:
        if component_id not in components:
            issues.append(
                f"required health component is missing: {component_id}"
            )
            failed = True
    for component_id, component in components.items():
        if component.observed_at > checked_at:
            issues.append(f"health component is future-dated: {component_id}")
            failed = True
        elif checked_at >= component.valid_until:
            issues.append(f"health component is expired: {component_id}")
            failed = True
        elif (
            checked_at - component.observed_at
        ).total_seconds() > policy.maximum_health_age_seconds:
            issues.append(f"health component is stale: {component_id}")
        if component.status == SupervisedProviderComponentStatus.FAILED:
            issues.append(f"health component failed: {component_id}")
            failed = True
        elif component.status == SupervisedProviderComponentStatus.DEGRADED:
            issues.append(f"health component degraded: {component_id}")

    status = (
        SupervisedDryRunHealthStatus.FAILED
        if failed
        else (
            SupervisedDryRunHealthStatus.DEGRADED
            if issues
            else SupervisedDryRunHealthStatus.HEALTHY
        )
    )
    return SupervisedDryRunHealthCheck(
        check_id=(
            f"{snapshot.snapshot_id}-"
            f"{sha256(checked_at.isoformat().encode()).hexdigest()[:16]}"
        ),
        service_id=policy.service_id,
        cycle_index=cycle_index,
        status=status,
        checked_at=checked_at,
        reasons=tuple(issues),
        evidence_refs=(
            *policy.evidence_refs,
            *snapshot.evidence_refs,
            *(
                ref
                for item in snapshot.components
                for ref in item.evidence_refs
            ),
        ),
    )


def resolve_supervised_request_envelope(
    *,
    policy: SupervisedProviderPolicy,
    authorization: AutonomousDryRunAuthorization,
    envelope: SupervisedRequestEnvelope,
    cycle_index: int,
    requested_at: datetime,
) -> AutonomousDryRunRequest:
    """Return one authorized fresh request or fail before service execution."""
    _require_aware(requested_at, "request evaluation time")
    issues: list[str] = []
    if envelope.service_id != policy.service_id:
        issues.append("request envelope references another service")
    if envelope.cycle_index != cycle_index:
        issues.append("request envelope references another cycle")
    if (
        envelope.request_source_id != policy.request_source_id
        or envelope.request_source_version != policy.request_source_version
    ):
        issues.append("request envelope source identity is not allowed")
    if (
        policy.authorization_id != authorization.authorization_id
        or policy.authorization_revision != authorization.revision
    ):
        issues.append("provider policy references another authorization")
    if (
        envelope.request.authorization_id != authorization.authorization_id
        or envelope.request.authorization_revision != authorization.revision
    ):
        issues.append("request references another authorization")
    if envelope.generated_at > requested_at:
        issues.append("request envelope is future-dated")
    elif requested_at >= envelope.valid_until:
        issues.append("request envelope is expired")
    elif (
        requested_at - envelope.generated_at
    ).total_seconds() > policy.maximum_request_age_seconds:
        issues.append("request envelope is stale")
    if envelope.request.evaluated_at != envelope.generated_at:
        issues.append(
            "request evaluation time does not match envelope generation"
        )
    if issues:
        raise ValueError("; ".join(issues))
    return envelope.request


def write_supervised_provider_policy(
    policy: SupervisedProviderPolicy, output_root: Path
) -> Path:
    """Write one immutable provider policy."""
    _require_safe_component(policy.service_id, "service ID")
    path = output_root / "policies" / f"{policy.service_id}.json"
    _write_model_exclusive(path, policy)
    return path


def write_supervised_health_snapshot(
    snapshot: SupervisedHealthSnapshot, output_root: Path
) -> Path:
    """Write one immutable provider health snapshot."""
    _require_safe_component(snapshot.snapshot_id, "health snapshot ID")
    path = output_root / "health-snapshots" / f"{snapshot.snapshot_id}.json"
    _write_model_exclusive(path, snapshot)
    return path


def write_supervised_request_envelope(
    envelope: SupervisedRequestEnvelope, output_root: Path
) -> Path:
    """Write one immutable fresh-request envelope."""
    _require_safe_component(envelope.envelope_id, "request envelope ID")
    path = output_root / "request-envelopes" / f"{envelope.envelope_id}.json"
    _write_model_exclusive(path, envelope)
    return path


def load_supervised_provider_policy(path: Path) -> SupervisedProviderPolicy:
    """Load one immutable provider policy."""
    return SupervisedProviderPolicy.model_validate_json(path.read_text())


def load_supervised_health_snapshot(path: Path) -> SupervisedHealthSnapshot:
    """Load one immutable provider health snapshot."""
    return SupervisedHealthSnapshot.model_validate_json(path.read_text())


def load_supervised_request_envelope(path: Path) -> SupervisedRequestEnvelope:
    """Load one immutable fresh-request envelope."""
    return SupervisedRequestEnvelope.model_validate_json(path.read_text())


def _require_aware(value: datetime, label: str) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{label} must be timezone-aware")


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
