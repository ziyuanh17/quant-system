"""Discover reviewed supervised-provider requests without running them."""

import json
import os
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.operator import (
    FiniteSupervisedProviderManifest,
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderDiscoveryResult,
    SupervisedProviderDiscoveryStatus,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.finite_supervised_provider import (
    finite_supervised_provider_manifest_for_paths,
)
from quant.workflows.supervised_provider_assembly_rehearsal import (
    load_and_verify_supervised_provider_assembly_rehearsal,
)
from quant.workflows.supervised_provider_operator import (
    load_supervised_provider_operator_request,
)

Clock = Callable[[], datetime]


def discover_supervised_provider_requests(
    *,
    policy: SupervisedProviderDiscoveryPolicy,
    output_root: Path,
    clock: Clock = lambda: datetime.now(UTC),
) -> SupervisedProviderDiscoveryResult:
    """Discover reviewed request files and write one finite-loop manifest."""
    policy_digest = _model_sha256(policy)
    result_path = output_root / "discoveries" / f"{policy.discovery_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{policy.discovery_id}.lock",
        lock_name=f"supervised-provider-discovery:{policy.discovery_id}",
        stale_after_seconds=300,
    ):
        _persist_or_verify_policy(policy, output_root)
        if result_path.exists():
            result = load_supervised_provider_discovery_result(result_path)
            if result.discovery_policy_sha256 != policy_digest:
                raise ValueError(
                    "supervised provider discovery ID is already bound"
                )
            verify_supervised_provider_discovery_result(result)
            return result

        discovered_at = _aware_now(clock)
        try:
            request_paths = _discover_request_paths(policy)
            if len(request_paths) > policy.maximum_requests:
                raise ValueError("provider discovery request limit exceeded")
            requests = tuple(
                load_supervised_provider_operator_request(path)
                for path in request_paths
            )
            _validate_request_set(requests)
            manifest_path = _write_finite_manifest(
                policy=policy,
                output_root=output_root,
                request_paths=request_paths,
                created_at=discovered_at,
            )
        except (OSError, ValueError) as error:
            result = SupervisedProviderDiscoveryResult(
                discovery_id=policy.discovery_id,
                discovery_policy_sha256=policy_digest,
                status=SupervisedProviderDiscoveryStatus.BLOCKED,
                discovered_at=discovered_at,
                blocked_reason=f"provider discovery blocked: {error}",
                evidence_refs=policy.evidence_refs,
            )
            _write_model_exclusive(result_path, result)
            return result

        result = SupervisedProviderDiscoveryResult(
            discovery_id=policy.discovery_id,
            discovery_policy_sha256=policy_digest,
            status=SupervisedProviderDiscoveryStatus.COMPLETED,
            discovered_at=discovered_at,
            request_paths=tuple(str(path) for path in request_paths),
            request_sha256s=tuple(_file_sha256(path) for path in request_paths),
            finite_manifest_path=str(manifest_path),
            finite_manifest_sha256=_file_sha256(manifest_path),
            evidence_refs=policy.evidence_refs,
        )
        _write_model_exclusive(result_path, result)
        return result


def write_supervised_provider_discovery_policy(
    policy: SupervisedProviderDiscoveryPolicy,
    output_root: Path,
) -> Path:
    """Write one immutable supervised-provider discovery policy."""
    path = output_root / "discovery-policies" / f"{policy.discovery_id}.json"
    _write_model_exclusive(path, policy)
    return path


def load_supervised_provider_discovery_policy(
    path: Path,
) -> SupervisedProviderDiscoveryPolicy:
    """Load one supervised-provider discovery policy."""
    return SupervisedProviderDiscoveryPolicy.model_validate_json(
        path.read_text()
    )


def load_supervised_provider_discovery_result(
    path: Path,
) -> SupervisedProviderDiscoveryResult:
    """Load one supervised-provider discovery result."""
    return SupervisedProviderDiscoveryResult.model_validate_json(
        path.read_text()
    )


def verify_supervised_provider_discovery_result(
    result: SupervisedProviderDiscoveryResult,
) -> None:
    """Verify one discovery result and directly linked immutable evidence."""
    for path_value, digest in zip(
        result.request_paths, result.request_sha256s, strict=True
    ):
        path = Path(path_value)
        if _file_sha256(path) != digest:
            raise ValueError("supervised provider discovery evidence changed")
        load_supervised_provider_operator_request(path)
    if result.finite_manifest_path is not None:
        path = Path(result.finite_manifest_path)
        if _file_sha256(path) != result.finite_manifest_sha256:
            raise ValueError("supervised provider discovery evidence changed")
        FiniteSupervisedProviderManifest.model_validate_json(path.read_text())


def _discover_request_paths(
    policy: SupervisedProviderDiscoveryPolicy,
) -> tuple[Path, ...]:
    directory = Path(policy.request_directory)
    if not directory.is_dir():
        raise ValueError("provider discovery request directory is missing")
    paths = tuple(sorted(path for path in directory.glob(policy.request_glob)))
    if not paths:
        raise ValueError("provider discovery found no reviewed requests")
    return paths


def _validate_request_set(
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
            raise ValueError(f"provider discovery {label} must be unique")
    for request in requests:
        if (
            _file_sha256(Path(request.assembly_manifest_path))
            != request.assembly_manifest_sha256
            or _file_sha256(Path(request.assembly_rehearsal_report_path))
            != request.assembly_rehearsal_report_sha256
        ):
            raise ValueError("provider discovery linked input hash mismatch")
        if request.service_policy.maximum_cycles != 1:
            raise ValueError(
                "provider discovery only accepts one-cycle requests"
            )
        if request.service_policy.interval_seconds != 0:
            raise ValueError(
                "provider discovery only accepts zero-interval requests"
            )
    for path_value in {
        request.assembly_rehearsal_report_path for request in requests
    }:
        report = load_and_verify_supervised_provider_assembly_rehearsal(
            Path(path_value)
        )
        if not report.passed:
            raise ValueError("provider discovery rehearsal did not pass")


def _write_finite_manifest(
    *,
    policy: SupervisedProviderDiscoveryPolicy,
    output_root: Path,
    request_paths: tuple[Path, ...],
    created_at: datetime,
) -> Path:
    manifest = finite_supervised_provider_manifest_for_paths(
        loop_id=policy.finite_loop_id,
        request_paths=request_paths,
        output_root=Path(policy.finite_output_root),
        created_at=created_at,
        evidence_refs=(
            f"provider-discovery:{policy.discovery_id}",
            *policy.evidence_refs,
        ),
    )
    path = output_root / "finite-manifests" / f"{manifest.loop_id}.json"
    if path.exists():
        if FiniteSupervisedProviderManifest.model_validate_json(
            path.read_text()
        ) != manifest:
            raise ValueError(
                "immutable discovered finite manifest conflicts"
            )
        return path
    _write_model_exclusive(path, manifest)
    return path


def _persist_or_verify_policy(
    policy: SupervisedProviderDiscoveryPolicy,
    output_root: Path,
) -> None:
    path = output_root / "discovery-policies" / f"{policy.discovery_id}.json"
    if path.exists():
        if load_supervised_provider_discovery_policy(path) != policy:
            raise ValueError(
                "immutable supervised provider discovery policy conflicts"
            )
        return
    _write_model_exclusive(path, policy)


def _aware_now(clock: Clock) -> datetime:
    value = clock()
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("supervised provider discovery clock must be aware")
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
