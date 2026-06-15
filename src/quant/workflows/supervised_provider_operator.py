"""Run one reviewed local provider assembly through the dry-run supervisor."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.operator import (
    SupervisedProviderOperatorRecord,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)
from quant.workflows.supervised_autonomous_dry_run import (
    load_supervised_dry_run_service_record,
    run_supervised_autonomous_dry_run_service,
)
from quant.workflows.supervised_provider_assembly import (
    assemble_local_supervised_provider_inputs,
    load_supervised_provider_assembly_manifest,
    load_supervised_provider_assembly_record,
)
from quant.workflows.supervised_provider_assembly_rehearsal import (
    SUPERVISED_PROVIDER_ASSEMBLY_REHEARSAL_POLICY,
    load_and_verify_supervised_provider_assembly_rehearsal,
)
from quant.workflows.supervised_provider_inputs import (
    evaluate_supervised_health_snapshot,
    load_supervised_health_snapshot,
    load_supervised_provider_policy,
    load_supervised_request_envelope,
    resolve_supervised_request_envelope,
)

Clock = Callable[[], datetime]


def run_supervised_provider_operator_request(
    *,
    request_path: Path,
    clock: Clock = lambda: datetime.now(UTC),
) -> SupervisedProviderOperatorRecord:
    """Run one exact reviewed assembly request and one supervised cycle."""
    request = load_supervised_provider_operator_request(request_path)
    output_root = Path(request.output_root)
    request_digest = _model_sha256(request)
    record_path = output_root / "operator-runs" / f"{request.request_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{request.request_id}.lock",
        lock_name=f"supervised-provider-operator:{request.request_id}",
        stale_after_seconds=300,
    ):
        request_artifact = _persist_or_verify_request(request, output_root)
        if record_path.exists():
            record = load_supervised_provider_operator_record(record_path)
            if record.request_sha256 != request_digest:
                raise ValueError(
                    "supervised provider operator request ID is already bound"
                )
            _verify_record_evidence(record)
            return record

        manifest_path = Path(request.assembly_manifest_path)
        rehearsal_path = Path(request.assembly_rehearsal_report_path)
        _require_hash(manifest_path, request.assembly_manifest_sha256)
        _require_hash(rehearsal_path, request.assembly_rehearsal_report_sha256)
        rehearsal = load_and_verify_supervised_provider_assembly_rehearsal(
            rehearsal_path
        )
        if (
            not rehearsal.passed
            or rehearsal.rehearsal_policy_version
            != SUPERVISED_PROVIDER_ASSEMBLY_REHEARSAL_POLICY
        ):
            raise ValueError("provider assembly rehearsal did not pass")

        manifest = load_supervised_provider_assembly_manifest(manifest_path)
        authorization = load_autonomous_dry_run_authorization(
            Path(manifest.authorization_path)
        )
        _validate_request_scope(
            request,
            manifest.service_id,
            manifest.cycle_index,
            authorization.authorization_id,
            authorization.revision,
        )
        assembly = assemble_local_supervised_provider_inputs(
            manifest=manifest,
            output_root=output_root / "assembly",
        )
        policy = load_supervised_provider_policy(
            Path(manifest.provider_policy_path)
        )
        health = load_supervised_health_snapshot(
            Path(assembly.health_snapshot_path)
        )
        envelope = load_supervised_request_envelope(
            Path(assembly.request_envelope_path)
        )
        service = run_supervised_autonomous_dry_run_service(
            policy=request.service_policy,
            authorization=authorization,
            health_provider=lambda cycle, now: (
                evaluate_supervised_health_snapshot(
                    policy=policy,
                    snapshot=health,
                    cycle_index=cycle,
                    checked_at=now,
                )
            ),
            request_provider=lambda cycle, now: (
                resolve_supervised_request_envelope(
                    policy=policy,
                    authorization=authorization,
                    envelope=envelope,
                    cycle_index=cycle,
                    requested_at=now,
                )
            ),
            shutdown_requested=lambda: False,
            output_root=output_root / "supervisor",
            clock=clock,
            sleeper=lambda _: None,
        )
        service_path = (
            output_root
            / "supervisor"
            / "services"
            / service.service_id
            / "record.json"
        )
        assembly_path = (
            output_root
            / "assembly"
            / "assemblies"
            / assembly.assembly_id
            / "record.json"
        )
        result = SupervisedProviderOperatorRecord(
            request_id=request.request_id,
            request_sha256=request_digest,
            assembly_id=assembly.assembly_id,
            service_id=service.service_id,
            service_status=service.status,
            assembly_record_path=str(assembly_path),
            assembly_record_sha256=_file_sha256(assembly_path),
            service_record_path=str(service_path),
            service_record_sha256=_file_sha256(service_path),
            completed_at=_aware_now(clock),
            evidence_refs=(
                str(request_artifact),
                str(manifest_path),
                str(rehearsal_path),
                *request.evidence_refs,
            ),
        )
        _write_model_exclusive(record_path, result)
        return result


def load_supervised_provider_operator_request(
    path: Path,
) -> SupervisedProviderOperatorRequest:
    """Load one reviewed assembly-to-supervisor operator request."""
    return SupervisedProviderOperatorRequest.model_validate_json(
        path.read_text()
    )


def write_supervised_provider_operator_request(
    request: SupervisedProviderOperatorRequest,
    output_root: Path,
) -> Path:
    """Write one immutable assembly-to-supervisor operator request."""
    path = output_root / f"{request.request_id}.json"
    _write_model_exclusive(path, request)
    return path


def load_supervised_provider_operator_record(
    path: Path,
) -> SupervisedProviderOperatorRecord:
    """Load one durable assembly-to-supervisor operator result."""
    return SupervisedProviderOperatorRecord.model_validate_json(
        path.read_text()
    )


def _validate_request_scope(
    request: SupervisedProviderOperatorRequest,
    service_id: str,
    cycle_index: int,
    authorization_id: str,
    authorization_revision: int,
) -> None:
    policy = request.service_policy
    if policy.service_id != service_id:
        raise ValueError("operator service policy references another service")
    if (
        policy.authorization_id != authorization_id
        or policy.authorization_revision != authorization_revision
    ):
        raise ValueError(
            "operator service policy references another authorization"
        )
    if cycle_index != 1:
        raise ValueError("operator assembly must be for cycle one")
    if policy.maximum_cycles != 1:
        raise ValueError("operator service policy must allow exactly one cycle")
    if policy.interval_seconds != 0:
        raise ValueError("operator service policy interval must be zero")


def _persist_or_verify_request(
    request: SupervisedProviderOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / "operator-requests" / f"{request.request_id}.json"
    if path.exists():
        if load_supervised_provider_operator_request(path) != request:
            raise ValueError("immutable supervised provider request conflicts")
        return path
    _write_model_exclusive(path, request)
    return path


def _verify_record_evidence(record: SupervisedProviderOperatorRecord) -> None:
    if (
        _file_sha256(Path(record.assembly_record_path))
        != record.assembly_record_sha256
        or _file_sha256(Path(record.service_record_path))
        != record.service_record_sha256
    ):
        raise ValueError("supervised provider operator evidence changed")
    assembly = load_supervised_provider_assembly_record(
        Path(record.assembly_record_path)
    )
    if (
        _file_sha256(Path(assembly.health_snapshot_path))
        != assembly.health_snapshot_sha256
        or _file_sha256(Path(assembly.request_envelope_path))
        != assembly.request_envelope_sha256
    ):
        raise ValueError("supervised provider operator evidence changed")
    service = load_supervised_dry_run_service_record(
        Path(record.service_record_path)
    )
    if (
        assembly.assembly_id != record.assembly_id
        or service.service_id != record.service_id
        or service.status != record.service_status
    ):
        raise ValueError("supervised provider operator evidence changed")


def _require_hash(path: Path, expected: str) -> None:
    if _file_sha256(path) != expected:
        raise ValueError(f"reviewed operator input hash does not match: {path}")


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("supervised provider operator clock must be aware")
    return value


def _model_sha256(model: BaseModel) -> str:
    payload = json.dumps(
        model.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode()
    return sha256(payload).hexdigest()


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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
