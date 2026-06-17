"""Test API-only reviewed request discovery for supervised providers."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest

from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderDiscoveryStatus,
    SupervisedProviderOperatorRequest,
)
from quant.workflows import (
    discover_supervised_provider_requests,
    load_finite_supervised_provider_manifest,
    load_supervised_provider_assembly_manifest,
    load_supervised_provider_discovery_result,
    run_finite_supervised_provider_loop,
    run_supervised_provider_assembly_local_rehearsal,
    verify_supervised_provider_discovery_result,
    write_supervised_provider_operator_request,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)


def test_provider_discovery_writes_manifest_without_running_requests(
    tmp_path,
) -> None:
    reviewed, requests = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    policy = _policy(tmp_path, reviewed)

    result = discover_supervised_provider_requests(
        policy=policy,
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )

    assert result.status == SupervisedProviderDiscoveryStatus.COMPLETED
    assert result.request_paths == tuple(
        str(path) for path in sorted(reviewed.glob("*.json"))
    )
    assert result.finite_manifest_path is not None
    manifest = load_finite_supervised_provider_manifest(
        Path(result.finite_manifest_path)
    )
    assert manifest.loop_id == policy.finite_loop_id
    assert manifest.request_paths == result.request_paths
    assert manifest.request_sha256s == result.request_sha256s
    assert not (tmp_path / "discovery-output" / "operator-runs").exists()
    assert all(
        not (Path(request.output_root) / "operator-runs").exists()
        for request in requests
    )


def test_provider_discovery_manifest_can_feed_finite_loop(tmp_path) -> None:
    reviewed, _ = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    result = discover_supervised_provider_requests(
        policy=_policy(tmp_path, reviewed),
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )
    assert result.finite_manifest_path is not None

    record = run_finite_supervised_provider_loop(
        manifest_path=Path(result.finite_manifest_path),
        clock=lambda: _now(),
    )

    assert set(record.completed_request_ids) == {
        "successful_assembly-discovery-request",
        "restart_reuse-discovery-request",
    }


def test_provider_discovery_restart_reuses_verified_result(tmp_path) -> None:
    reviewed, _ = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    policy = _policy(tmp_path, reviewed)
    output_root = tmp_path / "discovery-output"
    first = discover_supervised_provider_requests(
        policy=policy,
        output_root=output_root,
        clock=lambda: _now(),
    )

    second = discover_supervised_provider_requests(
        policy=policy,
        output_root=output_root,
        clock=lambda: _now(),
    )

    assert second == first
    assert (
        load_supervised_provider_discovery_result(
            output_root / "discoveries" / "provider-discovery-1.json"
        )
        == first
    )


def test_provider_discovery_recovers_existing_manifest_before_result(
    tmp_path,
) -> None:
    reviewed, _ = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    policy = _policy(tmp_path, reviewed)
    output_root = tmp_path / "discovery-output"
    first = discover_supervised_provider_requests(
        policy=policy,
        output_root=output_root,
        clock=lambda: _now(),
    )
    result_path = output_root / "discoveries" / "provider-discovery-1.json"
    result_path.unlink()

    recovered = discover_supervised_provider_requests(
        policy=policy,
        output_root=output_root,
        clock=lambda: _now(),
    )

    assert recovered == first


def test_provider_discovery_blocks_empty_directory(tmp_path) -> None:
    result = discover_supervised_provider_requests(
        policy=_policy(tmp_path, tmp_path / "reviewed"),
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )

    assert result.status == SupervisedProviderDiscoveryStatus.BLOCKED
    assert "request directory is missing" in str(result.blocked_reason)
    assert result.finite_manifest_path is None


def test_provider_discovery_blocks_over_limit(tmp_path) -> None:
    reviewed, _ = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    result = discover_supervised_provider_requests(
        policy=_policy(tmp_path, reviewed, maximum_requests=1),
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )

    assert result.status == SupervisedProviderDiscoveryStatus.BLOCKED
    assert "request limit exceeded" in str(result.blocked_reason)
    assert not (tmp_path / "discovery-output" / "finite-manifests").exists()


def test_provider_discovery_blocks_changed_linked_input(tmp_path) -> None:
    reviewed, requests = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    manifest_path = Path(requests[1].assembly_manifest_path)
    manifest_path.write_text(manifest_path.read_text() + " ")

    result = discover_supervised_provider_requests(
        policy=_policy(tmp_path, reviewed),
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )

    assert result.status == SupervisedProviderDiscoveryStatus.BLOCKED
    assert "linked input hash mismatch" in str(result.blocked_reason)


def test_provider_discovery_detects_changed_completed_evidence(
    tmp_path,
) -> None:
    reviewed, _ = _reviewed_requests(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    result = discover_supervised_provider_requests(
        policy=_policy(tmp_path, reviewed),
        output_root=tmp_path / "discovery-output",
        clock=lambda: _now(),
    )
    request_path = Path(result.request_paths[0])
    request_path.write_text(request_path.read_text() + " ")

    with pytest.raises(ValueError, match="discovery evidence changed"):
        verify_supervised_provider_discovery_result(result)


def test_provider_discovery_policy_rejects_broad_glob(tmp_path) -> None:
    with pytest.raises(ValueError, match="only supports"):
        SupervisedProviderDiscoveryPolicy(
            discovery_id="provider-discovery-1",
            discovery_policy_version="supervised_provider_discovery_v1",
            request_directory=str(tmp_path / "reviewed"),
            request_glob="**/*.json",
            maximum_requests=2,
            finite_loop_id="discovered-finite-loop",
            finite_output_root=str(tmp_path / "finite-output"),
            created_at=_now(),
        )


def _reviewed_requests(
    root: Path,
    scenarios: tuple[str, ...],
) -> tuple[Path, tuple[SupervisedProviderOperatorRequest, ...]]:
    now = _now()
    prerequisite_root = root / "prerequisite"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="discovery-prerequisite",
        output_root=prerequisite_root,
        evaluated_at=now,
    )
    report_path = prerequisite_root / "reports" / "discovery-prerequisite.json"
    reviewed = root / "reviewed"
    requests = tuple(
        _request(root, prerequisite_root, report_path, scenario, now)
        for scenario in scenarios
    )
    for request in requests:
        write_supervised_provider_operator_request(request, reviewed)
    return reviewed, requests


def _request(
    root: Path,
    prerequisite_root: Path,
    report_path: Path,
    scenario: str,
    now: datetime,
) -> SupervisedProviderOperatorRequest:
    manifest_path = (
        prerequisite_root
        / "scenarios"
        / scenario
        / "output"
        / "assemblies"
        / f"{scenario}-assembly"
        / "manifest.json"
    )
    manifest = load_supervised_provider_assembly_manifest(manifest_path)
    authorization = load_autonomous_dry_run_authorization(
        Path(manifest.authorization_path)
    )
    return SupervisedProviderOperatorRequest(
        request_id=f"{scenario}-discovery-request",
        assembly_manifest_path=str(manifest_path),
        assembly_manifest_sha256=_sha256(manifest_path),
        assembly_rehearsal_report_path=str(report_path),
        assembly_rehearsal_report_sha256=_sha256(report_path),
        service_policy=SupervisedDryRunServicePolicy(
            service_id=manifest.service_id,
            policy_version="bounded_supervised_dry_run_v1",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            maximum_cycles=1,
            interval_seconds=0,
            maximum_runtime_seconds=60,
            created_at=now,
        ),
        output_root=str(root / "request-outputs" / scenario),
        created_at=now,
        evidence_refs=("provider-discovery:test",),
    )


def _policy(
    root: Path,
    reviewed: Path,
    maximum_requests: int = 2,
) -> SupervisedProviderDiscoveryPolicy:
    return SupervisedProviderDiscoveryPolicy(
        discovery_id="provider-discovery-1",
        discovery_policy_version="supervised_provider_discovery_v1",
        request_directory=str(reviewed),
        maximum_requests=maximum_requests,
        finite_loop_id="discovered-finite-loop",
        finite_output_root=str(root / "finite-output"),
        created_at=_now(),
        evidence_refs=("provider-discovery:test",),
    )


def _now() -> datetime:
    return datetime(2026, 6, 16, 15, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
