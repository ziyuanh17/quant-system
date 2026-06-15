"""Run one finite ordered list of fresh supervised-provider dry-run requests."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import SupervisedDryRunServiceStatus
from quant.models.operator import (
    FiniteSupervisedProviderManifest,
    FiniteSupervisedProviderRecord,
    FiniteSupervisedProviderStatus,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.supervised_provider_assembly_rehearsal import (
    load_and_verify_supervised_provider_assembly_rehearsal,
)
from quant.workflows.supervised_provider_operator import (
    load_supervised_provider_operator_record,
    load_supervised_provider_operator_request,
    run_supervised_provider_operator_request,
    verify_supervised_provider_operator_record,
)

Clock = Callable[[], datetime]


def run_finite_supervised_provider_loop(
    *,
    manifest_path: Path,
    clock: Clock = lambda: datetime.now(UTC),
) -> FiniteSupervisedProviderRecord:
    """Run exact fresh requests in order and stop on the first block."""
    manifest = load_finite_supervised_provider_manifest(manifest_path)
    output_root = Path(manifest.output_root)
    manifest_digest = _model_sha256(manifest)
    record_path = output_root / "loops" / f"{manifest.loop_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{manifest.loop_id}.lock",
        lock_name=f"finite-supervised-provider:{manifest.loop_id}",
        stale_after_seconds=300,
    ):
        _persist_or_verify_manifest(manifest, output_root)
        requests = _load_verified_requests(manifest)
        _validate_request_set(manifest, requests)
        if record_path.exists():
            record = load_finite_supervised_provider_record(record_path)
            if record.manifest_sha256 != manifest_digest:
                raise ValueError(
                    "finite provider loop ID is bound to other inputs"
                )
            _verify_record_evidence(record)
            return record

        started_at = _aware_now(clock)
        completed_ids: list[str] = []
        record_paths: list[str] = []
        record_sha256s: list[str] = []
        blocked_request_id: str | None = None
        blocked_record_path: str | None = None
        blocked_record_sha256: str | None = None
        reason = "finite supervised-provider loop completed"
        for request_path, request in zip(
            manifest.request_paths, requests, strict=True
        ):
            try:
                operator = run_supervised_provider_operator_request(
                    request_path=Path(request_path),
                    clock=clock,
                )
            except (OSError, ValueError) as error:
                blocked_request_id = request.request_id
                reason = f"finite supervised-provider loop blocked: {error}"
                break
            if (
                operator.service_status
                != SupervisedDryRunServiceStatus.COMPLETED
            ):
                blocked_request_id = request.request_id
                path = (
                    Path(request.output_root)
                    / "operator-runs"
                    / f"{request.request_id}.json"
                )
                blocked_record_path = str(path)
                blocked_record_sha256 = _file_sha256(path)
                reason = (
                    "finite supervised-provider loop stopped on "
                    f"{operator.service_status.value} service"
                )
                break
            path = (
                Path(request.output_root)
                / "operator-runs"
                / f"{request.request_id}.json"
            )
            completed_ids.append(request.request_id)
            record_paths.append(str(path))
            record_sha256s.append(_file_sha256(path))

        result = FiniteSupervisedProviderRecord(
            loop_id=manifest.loop_id,
            manifest_sha256=manifest_digest,
            status=(
                FiniteSupervisedProviderStatus.BLOCKED
                if blocked_request_id is not None
                else FiniteSupervisedProviderStatus.COMPLETED
            ),
            requested_count=len(requests),
            completed_request_ids=tuple(completed_ids),
            operator_record_paths=tuple(record_paths),
            operator_record_sha256s=tuple(record_sha256s),
            blocked_request_id=blocked_request_id,
            blocked_operator_record_path=blocked_record_path,
            blocked_operator_record_sha256=blocked_record_sha256,
            started_at=started_at,
            completed_at=_aware_now(clock),
            reason=reason,
        )
        _write_model_exclusive(record_path, result)
        return result


def finite_supervised_provider_manifest_for_paths(
    *,
    loop_id: str,
    request_paths: tuple[Path, ...],
    output_root: Path,
    created_at: datetime,
    evidence_refs: tuple[str, ...] = (),
) -> FiniteSupervisedProviderManifest:
    """Build one finite manifest bound to exact operator request files."""
    return FiniteSupervisedProviderManifest(
        loop_id=loop_id,
        request_paths=tuple(str(path) for path in request_paths),
        request_sha256s=tuple(_file_sha256(path) for path in request_paths),
        output_root=str(output_root),
        created_at=created_at,
        evidence_refs=evidence_refs,
    )


def write_finite_supervised_provider_manifest(
    manifest: FiniteSupervisedProviderManifest,
    output_root: Path,
) -> Path:
    """Write one immutable finite supervised-provider manifest."""
    path = output_root / f"{manifest.loop_id}.json"
    _write_model_exclusive(path, manifest)
    return path


def load_finite_supervised_provider_manifest(
    path: Path,
) -> FiniteSupervisedProviderManifest:
    """Load one finite supervised-provider manifest."""
    return FiniteSupervisedProviderManifest.model_validate_json(
        path.read_text()
    )


def load_finite_supervised_provider_record(
    path: Path,
) -> FiniteSupervisedProviderRecord:
    """Load one durable finite supervised-provider summary."""
    return FiniteSupervisedProviderRecord.model_validate_json(path.read_text())


def _load_verified_requests(
    manifest: FiniteSupervisedProviderManifest,
) -> tuple[SupervisedProviderOperatorRequest, ...]:
    requests = []
    for path_value, digest in zip(
        manifest.request_paths, manifest.request_sha256s, strict=True
    ):
        path = Path(path_value)
        if _file_sha256(path) != digest:
            raise ValueError("finite provider request hash does not match")
        requests.append(load_supervised_provider_operator_request(path))
    return tuple(requests)


def _validate_request_set(
    manifest: FiniteSupervisedProviderManifest,
    requests: tuple[SupervisedProviderOperatorRequest, ...],
) -> None:
    identities = {
        "request IDs": tuple(item.request_id for item in requests),
        "assembly manifests": tuple(
            item.assembly_manifest_path for item in requests
        ),
        "service IDs": tuple(
            item.service_policy.service_id for item in requests
        ),
        "output roots": tuple(item.output_root for item in requests),
    }
    for label, values in identities.items():
        if len(set(values)) != len(values):
            raise ValueError(f"finite provider {label} must be unique")
    if manifest.output_root in identities["output roots"]:
        raise ValueError("finite provider loop output root must be separate")
    roots = (manifest.output_root, *identities["output roots"])
    for index, first in enumerate(roots):
        for second in roots[index + 1 :]:
            if _paths_overlap(Path(first), Path(second)):
                raise ValueError(
                    "finite provider output roots must not overlap"
                )
    verified_rehearsals: set[str] = set()
    for request in requests:
        if (
            _file_sha256(Path(request.assembly_manifest_path))
            != request.assembly_manifest_sha256
            or _file_sha256(Path(request.assembly_rehearsal_report_path))
            != request.assembly_rehearsal_report_sha256
        ):
            raise ValueError("finite provider linked input hash does not match")
        if request.assembly_rehearsal_report_path not in verified_rehearsals:
            report = load_and_verify_supervised_provider_assembly_rehearsal(
                Path(request.assembly_rehearsal_report_path)
            )
            if not report.passed:
                raise ValueError(
                    "finite provider assembly rehearsal did not pass"
                )
            verified_rehearsals.add(request.assembly_rehearsal_report_path)


def _persist_or_verify_manifest(
    manifest: FiniteSupervisedProviderManifest,
    output_root: Path,
) -> None:
    path = output_root / "manifests" / f"{manifest.loop_id}.json"
    if path.exists():
        if load_finite_supervised_provider_manifest(path) != manifest:
            raise ValueError(
                "immutable finite supervised-provider manifest conflicts"
            )
        return
    _write_model_exclusive(path, manifest)


def _verify_record_evidence(record: FiniteSupervisedProviderRecord) -> None:
    for path_value, digest in zip(
        record.operator_record_paths,
        record.operator_record_sha256s,
        strict=True,
    ):
        path = Path(path_value)
        if _file_sha256(path) != digest:
            raise ValueError("finite supervised-provider evidence changed")
        operator = load_supervised_provider_operator_record(path)
        verify_supervised_provider_operator_record(operator)
    if record.blocked_operator_record_path is not None:
        path = Path(record.blocked_operator_record_path)
        if _file_sha256(path) != record.blocked_operator_record_sha256:
            raise ValueError("finite supervised-provider evidence changed")
        operator = load_supervised_provider_operator_record(path)
        verify_supervised_provider_operator_record(operator)


def _paths_overlap(first: Path, second: Path) -> bool:
    first_resolved = first.resolve()
    second_resolved = second.resolve()
    return (
        first_resolved == second_resolved
        or first_resolved in second_resolved.parents
        or second_resolved in first_resolved.parents
    )


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("finite supervised-provider clock must be aware")
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
