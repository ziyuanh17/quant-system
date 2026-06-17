"""Run one reviewed supervised-provider discovery request from the CLI."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.operator import (
    SupervisedProviderDiscoveryOperatorRecord,
    SupervisedProviderDiscoveryOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.supervised_provider_discovery import (
    discover_supervised_provider_requests,
    load_supervised_provider_discovery_result,
    verify_supervised_provider_discovery_result,
)
from quant.workflows.supervised_provider_discovery_rehearsal import (
    SUPERVISED_PROVIDER_DISCOVERY_REHEARSAL_POLICY,
    load_and_verify_supervised_provider_discovery_rehearsal,
)

Clock = Callable[[], datetime]


def run_supervised_provider_discovery_operator_request(
    *,
    request_path: Path,
    clock: Clock = lambda: datetime.now(UTC),
) -> SupervisedProviderDiscoveryOperatorRecord:
    """Run one reviewed discovery-only request and write one record."""
    request = load_supervised_provider_discovery_operator_request(request_path)
    output_root = Path(request.output_root)
    request_digest = _model_sha256(request)
    record_path = (
        output_root / "operator-runs" / f"{request.request_id}.json"
    )
    with FileLock(
        path=output_root / "locks" / f"{request.request_id}.lock",
        lock_name=f"supervised-provider-discovery-operator:{request.request_id}",
        stale_after_seconds=300,
    ):
        request_artifact = _persist_or_verify_request(request, output_root)
        if record_path.exists():
            record = load_supervised_provider_discovery_operator_record(
                record_path
            )
            if record.request_sha256 != request_digest:
                raise ValueError(
                    "supervised provider discovery request ID is already bound"
                )
            verify_supervised_provider_discovery_operator_record(record)
            return record

        rehearsal_path = Path(request.discovery_rehearsal_report_path)
        _require_hash(
            rehearsal_path, request.discovery_rehearsal_report_sha256
        )
        rehearsal = load_and_verify_supervised_provider_discovery_rehearsal(
            rehearsal_path
        )
        if (
            not rehearsal.passed
            or rehearsal.rehearsal_policy_version
            != SUPERVISED_PROVIDER_DISCOVERY_REHEARSAL_POLICY
        ):
            raise ValueError("provider discovery rehearsal did not pass")

        discovery = discover_supervised_provider_requests(
            policy=request.discovery_policy,
            output_root=output_root / "discovery",
            clock=clock,
        )
        discovery_path = (
            output_root
            / "discovery"
            / "discoveries"
            / f"{discovery.discovery_id}.json"
        )
        record = SupervisedProviderDiscoveryOperatorRecord(
            request_id=request.request_id,
            request_sha256=request_digest,
            discovery_id=discovery.discovery_id,
            discovery_status=discovery.status,
            discovery_result_path=str(discovery_path),
            discovery_result_sha256=_file_sha256(discovery_path),
            finite_manifest_path=discovery.finite_manifest_path,
            finite_manifest_sha256=discovery.finite_manifest_sha256,
            completed_at=_aware_now(clock),
            evidence_refs=(
                str(request_artifact),
                str(rehearsal_path),
                *request.evidence_refs,
            ),
        )
        _write_model_exclusive(record_path, record)
        return record


def load_supervised_provider_discovery_operator_request(
    path: Path,
) -> SupervisedProviderDiscoveryOperatorRequest:
    """Load one reviewed discovery-only operator request."""
    return SupervisedProviderDiscoveryOperatorRequest.model_validate_json(
        path.read_text()
    )


def write_supervised_provider_discovery_operator_request(
    request: SupervisedProviderDiscoveryOperatorRequest,
    output_root: Path,
) -> Path:
    """Write one immutable discovery-only operator request."""
    path = output_root / f"{request.request_id}.json"
    _write_model_exclusive(path, request)
    return path


def load_supervised_provider_discovery_operator_record(
    path: Path,
) -> SupervisedProviderDiscoveryOperatorRecord:
    """Load one discovery-only operator result."""
    return SupervisedProviderDiscoveryOperatorRecord.model_validate_json(
        path.read_text()
    )


def verify_supervised_provider_discovery_operator_record(
    record: SupervisedProviderDiscoveryOperatorRecord,
) -> None:
    """Verify one discovery-only operator record and linked evidence."""
    if (
        _file_sha256(Path(record.discovery_result_path))
        != record.discovery_result_sha256
    ):
        raise ValueError(
            "supervised provider discovery operator evidence changed"
        )
    discovery = load_supervised_provider_discovery_result(
        Path(record.discovery_result_path)
    )
    verify_supervised_provider_discovery_result(discovery)
    if (
        discovery.discovery_id != record.discovery_id
        or discovery.status != record.discovery_status
        or discovery.finite_manifest_path != record.finite_manifest_path
        or discovery.finite_manifest_sha256 != record.finite_manifest_sha256
    ):
        raise ValueError(
            "supervised provider discovery operator evidence changed"
        )


def _persist_or_verify_request(
    request: SupervisedProviderDiscoveryOperatorRequest,
    output_root: Path,
) -> Path:
    path = (
        output_root
        / "operator-requests"
        / f"{request.request_id}.json"
    )
    if path.exists():
        if load_supervised_provider_discovery_operator_request(path) != request:
            raise ValueError(
                "immutable supervised provider discovery request conflicts"
            )
        return path
    _write_model_exclusive(path, request)
    return path


def _require_hash(path: Path, expected: str) -> None:
    if _file_sha256(path) != expected:
        raise ValueError(
            f"reviewed discovery input hash does not match: {path}"
        )


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "supervised provider discovery operator clock must be aware"
        )
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
