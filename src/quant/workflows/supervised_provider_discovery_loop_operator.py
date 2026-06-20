"""Run one reviewed discovery-to-finite-loop composition."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.operator import (
    FiniteSupervisedProviderStatus,
    SupervisedProviderDiscoveryLoopOperatorRecord,
    SupervisedProviderDiscoveryLoopOperatorRequest,
    SupervisedProviderDiscoveryLoopStatus,
    SupervisedProviderDiscoveryStatus,
)
from quant.operations import FileLock
from quant.workflows.finite_supervised_provider import (
    load_finite_supervised_provider_manifest,
    load_finite_supervised_provider_record,
    run_finite_supervised_provider_loop,
)
from quant.workflows.supervised_provider_discovery_operator import (
    load_supervised_provider_discovery_operator_record,
    load_supervised_provider_discovery_operator_request,
    run_supervised_provider_discovery_operator_request,
    verify_supervised_provider_discovery_operator_record,
)
from quant.workflows.supervised_provider_discovery_operator_rehearsal import (
    SUPERVISED_PROVIDER_DISCOVERY_OPERATOR_REHEARSAL_POLICY,
    load_and_verify_supervised_provider_discovery_operator_rehearsal,
)

Clock = Callable[[], datetime]


def run_supervised_provider_discovery_loop_operator_request(
    *,
    request_path: Path,
    clock: Clock = lambda: datetime.now(UTC),
) -> SupervisedProviderDiscoveryLoopOperatorRecord:
    """Run discovery, then the exact generated finite manifest if available."""
    request = load_supervised_provider_discovery_loop_operator_request(
        request_path
    )
    output_root = Path(request.output_root)
    request_digest = _model_sha256(request)
    record_path = output_root / "operator-runs" / f"{request.request_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{request.request_id}.lock",
        lock_name=f"supervised-provider-discovery-loop:{request.request_id}",
        stale_after_seconds=300,
    ):
        request_artifact = _persist_or_verify_request(request, output_root)
        if record_path.exists():
            record = load_supervised_provider_discovery_loop_operator_record(
                record_path
            )
            if record.request_sha256 != request_digest:
                raise ValueError(
                    "supervised provider discovery-loop request ID is bound"
                )
            verify_supervised_provider_discovery_loop_operator_record(record)
            return record

        discovery_request_path = Path(request.discovery_operator_request_path)
        rehearsal_path = Path(
            request.discovery_operator_rehearsal_report_path
        )
        _require_hash(
            discovery_request_path,
            request.discovery_operator_request_sha256,
        )
        _require_hash(
            rehearsal_path,
            request.discovery_operator_rehearsal_report_sha256,
        )
        rehearsal = (
            load_and_verify_supervised_provider_discovery_operator_rehearsal(
                rehearsal_path
            )
        )
        if (
            not rehearsal.passed
            or rehearsal.rehearsal_policy_version
            != SUPERVISED_PROVIDER_DISCOVERY_OPERATOR_REHEARSAL_POLICY
        ):
            raise ValueError(
                "provider discovery operator rehearsal did not pass"
            )

        discovery_record = run_supervised_provider_discovery_operator_request(
            request_path=discovery_request_path,
            clock=clock,
        )
        discovery_record_path = _discovery_operator_record_path(
            discovery_request_path
        )
        status = SupervisedProviderDiscoveryLoopStatus.BLOCKED
        finite_manifest_path: str | None = None
        finite_manifest_sha256: str | None = None
        finite_loop_record_path: str | None = None
        finite_loop_record_sha256: str | None = None
        reason = "discovery-loop blocked before finite loop"
        if (
            discovery_record.discovery_status
            == SupervisedProviderDiscoveryStatus.COMPLETED
        ):
            if discovery_record.finite_manifest_path is None:
                raise ValueError("completed discovery did not provide manifest")
            finite_manifest_path = discovery_record.finite_manifest_path
            finite_manifest_sha256 = discovery_record.finite_manifest_sha256
            loop = run_finite_supervised_provider_loop(
                manifest_path=Path(finite_manifest_path),
                clock=clock,
            )
            manifest = load_finite_supervised_provider_manifest(
                Path(finite_manifest_path)
            )
            loop_path = (
                Path(manifest.output_root)
                / "loops"
                / f"{manifest.loop_id}.json"
            )
            finite_loop_record_path = str(loop_path)
            finite_loop_record_sha256 = _file_sha256(loop_path)
            status = (
                SupervisedProviderDiscoveryLoopStatus.COMPLETED
                if loop.status == FiniteSupervisedProviderStatus.COMPLETED
                else SupervisedProviderDiscoveryLoopStatus.BLOCKED
            )
            reason = (
                "discovery-loop completed"
                if status == SupervisedProviderDiscoveryLoopStatus.COMPLETED
                else f"finite loop blocked: {loop.reason}"
            )
        else:
            reason = "discovery blocked before finite loop"

        record = SupervisedProviderDiscoveryLoopOperatorRecord(
            request_id=request.request_id,
            request_sha256=request_digest,
            status=status,
            discovery_operator_record_path=str(discovery_record_path),
            discovery_operator_record_sha256=_file_sha256(
                discovery_record_path
            ),
            finite_manifest_path=finite_manifest_path,
            finite_manifest_sha256=finite_manifest_sha256,
            finite_loop_record_path=finite_loop_record_path,
            finite_loop_record_sha256=finite_loop_record_sha256,
            completed_at=_aware_now(clock),
            reason=reason,
            evidence_refs=(
                str(request_artifact),
                str(discovery_request_path),
                str(rehearsal_path),
                *request.evidence_refs,
            ),
        )
        _write_model_exclusive(record_path, record)
        return record


def load_supervised_provider_discovery_loop_operator_request(
    path: Path,
) -> SupervisedProviderDiscoveryLoopOperatorRequest:
    """Load one reviewed discovery-to-loop request."""
    return SupervisedProviderDiscoveryLoopOperatorRequest.model_validate_json(
        path.read_text()
    )


def write_supervised_provider_discovery_loop_operator_request(
    request: SupervisedProviderDiscoveryLoopOperatorRequest,
    output_root: Path,
) -> Path:
    """Write one immutable discovery-to-loop request."""
    path = output_root / f"{request.request_id}.json"
    _write_model_exclusive(path, request)
    return path


def load_supervised_provider_discovery_loop_operator_record(
    path: Path,
) -> SupervisedProviderDiscoveryLoopOperatorRecord:
    """Load one discovery-to-loop composition result."""
    return SupervisedProviderDiscoveryLoopOperatorRecord.model_validate_json(
        path.read_text()
    )


def verify_supervised_provider_discovery_loop_operator_record(
    record: SupervisedProviderDiscoveryLoopOperatorRecord,
) -> None:
    """Verify one discovery-to-loop record and linked evidence."""
    if (
        _file_sha256(Path(record.discovery_operator_record_path))
        != record.discovery_operator_record_sha256
    ):
        raise ValueError("discovery-loop operator evidence changed")
    discovery_record = load_supervised_provider_discovery_operator_record(
        Path(record.discovery_operator_record_path)
    )
    verify_supervised_provider_discovery_operator_record(discovery_record)
    if record.finite_manifest_path is not None:
        _require_hash(
            Path(record.finite_manifest_path),
            record.finite_manifest_sha256 or "",
        )
        load_finite_supervised_provider_manifest(
            Path(record.finite_manifest_path)
        )
    if record.finite_loop_record_path is not None:
        _require_hash(
            Path(record.finite_loop_record_path),
            record.finite_loop_record_sha256 or "",
        )
        load_finite_supervised_provider_record(
            Path(record.finite_loop_record_path)
        )


def _persist_or_verify_request(
    request: SupervisedProviderDiscoveryLoopOperatorRequest,
    output_root: Path,
) -> Path:
    path = output_root / "operator-requests" / f"{request.request_id}.json"
    if path.exists():
        if load_supervised_provider_discovery_loop_operator_request(
            path
        ) != request:
            raise ValueError(
                "immutable supervised provider discovery-loop request conflicts"
            )
        return path
    _write_model_exclusive(path, request)
    return path


def _discovery_operator_record_path(request_path: Path) -> Path:
    request = load_supervised_provider_discovery_operator_request(request_path)
    return (
        Path(request.output_root)
        / "operator-runs"
        / f"{request.request_id}.json"
    )


def _require_hash(path: Path, expected: str) -> None:
    if _file_sha256(path) != expected:
        raise ValueError(f"reviewed discovery-loop hash does not match: {path}")


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(
            "supervised provider discovery-loop clock must be aware"
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
