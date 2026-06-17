"""Test manually started supervised-provider discovery operator boundary."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    SupervisedProviderDiscoveryOperatorRequest,
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderDiscoveryStatus,
    SupervisedProviderOperatorRequest,
)
from quant.workflows import (
    load_supervised_provider_assembly_manifest,
    load_supervised_provider_discovery_operator_record,
    run_supervised_provider_assembly_local_rehearsal,
    run_supervised_provider_discovery_handoff_rehearsal,
    run_supervised_provider_discovery_operator_request,
    verify_supervised_provider_discovery_operator_record,
    write_supervised_provider_discovery_operator_request,
    write_supervised_provider_operator_request,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)


def test_discovery_operator_writes_manifest_without_running_loop(
    tmp_path,
) -> None:
    request_path, output_root, _ = _operator_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    record = run_supervised_provider_discovery_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert (
        record.discovery_status
        == SupervisedProviderDiscoveryStatus.COMPLETED
    )
    assert record.finite_manifest_path is not None
    assert not (output_root / "loop-output").exists()
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()
    verify_supervised_provider_discovery_operator_record(record)


def test_discovery_operator_restart_returns_verified_record(tmp_path) -> None:
    request_path, output_root, _ = _operator_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    first = run_supervised_provider_discovery_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    second = run_supervised_provider_discovery_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert second == first
    assert (
        load_supervised_provider_discovery_operator_record(
            output_root / "operator-runs" / "discovery-operator-request.json"
        )
        == first
    )


def test_discovery_operator_rejects_changed_rehearsal_report(tmp_path) -> None:
    request_path, _, request = _operator_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    Path(request.discovery_rehearsal_report_path).write_text(
        Path(request.discovery_rehearsal_report_path).read_text() + " "
    )

    with pytest.raises(ValueError, match="input hash does not match"):
        run_supervised_provider_discovery_operator_request(
            request_path=request_path,
            clock=lambda: _now(),
        )


def test_discovery_operator_cli_runs_discovery_only(tmp_path) -> None:
    request_path, output_root, _ = _operator_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "supervised-provider-discover",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code == 0
    assert "Status: completed" in result.output
    assert "Finite manifest:" in result.output
    assert not (output_root / "loop-output").exists()
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()


def test_discovery_operator_cli_exits_nonzero_when_discovery_blocks(
    tmp_path,
) -> None:
    request_path, _, _ = _operator_request(
        tmp_path,
        ("successful_assembly", "restart_reuse"),
        maximum_requests=1,
    )

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "supervised-provider-discover",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code == 1
    assert "Status: blocked" in result.output


def test_discovery_operator_cli_has_no_operational_selectors() -> None:
    result = CliRunner().invoke(
        app, ["dry-run", "supervised-provider-discover", "--help"]
    )

    assert result.exit_code == 0
    assert "--request-path" in result.output
    assert "--output-root" not in result.output
    assert "--iterations" not in result.output
    assert "--mode" not in result.output
    assert "broker" not in result.output.lower()
    assert "alpaca" not in result.output.lower()
    assert "paper" not in result.output.lower()
    assert "scheduler" not in result.output.lower()
    assert "runtime" not in result.output.lower()


def _operator_request(
    root: Path,
    scenarios: tuple[str, ...],
    maximum_requests: int = 2,
) -> tuple[Path, Path, SupervisedProviderDiscoveryOperatorRequest]:
    now = _now()
    rehearsal_root = root / "discovery-rehearsal"
    run_supervised_provider_discovery_handoff_rehearsal(
        rehearsal_id="operator-prerequisite",
        output_root=rehearsal_root,
        evaluated_at=now,
    )
    rehearsal_path = (
        rehearsal_root / "reports" / "operator-prerequisite.json"
    )
    reviewed, _ = _reviewed_requests(root, scenarios, now)
    output_root = root / "operator-output"
    request = SupervisedProviderDiscoveryOperatorRequest(
        request_id="discovery-operator-request",
        discovery_policy=SupervisedProviderDiscoveryPolicy(
            discovery_id="operator-discovery",
            discovery_policy_version="supervised_provider_discovery_v1",
            request_directory=str(reviewed),
            maximum_requests=maximum_requests,
            finite_loop_id="operator-discovered-loop",
            finite_output_root=str(output_root / "loop-output"),
            created_at=now,
            evidence_refs=("discovery-operator:test",),
        ),
        output_root=str(output_root),
        discovery_rehearsal_report_path=str(rehearsal_path),
        discovery_rehearsal_report_sha256=_sha256(rehearsal_path),
        created_at=now,
        evidence_refs=("discovery-operator:test",),
    )
    return (
        write_supervised_provider_discovery_operator_request(
            request, root / "reviewed-discovery"
        ),
        output_root,
        request,
    )


def _reviewed_requests(
    root: Path,
    scenarios: tuple[str, ...],
    now: datetime,
) -> tuple[Path, tuple[SupervisedProviderOperatorRequest, ...]]:
    prerequisite_root = root / "assembly-prerequisite"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="discovery-operator-assembly",
        output_root=prerequisite_root,
        evaluated_at=now,
    )
    report_path = (
        prerequisite_root / "reports" / "discovery-operator-assembly.json"
    )
    reviewed = root / "reviewed-requests"
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
        request_id=f"{scenario}-operator-discovery-request",
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
        evidence_refs=("discovery-operator:test",),
    )


def _now() -> datetime:
    return datetime(2026, 6, 17, 15, 0, tzinfo=UTC)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
