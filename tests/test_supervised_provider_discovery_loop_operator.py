"""Test manually started supervised-provider discovery-to-loop composition."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from typer.testing import CliRunner

from quant.cli import app
from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    SupervisedProviderDiscoveryLoopOperatorRequest,
    SupervisedProviderDiscoveryLoopStatus,
    SupervisedProviderDiscoveryOperatorRequest,
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderOperatorRequest,
)
from quant.workflows import (
    load_supervised_provider_assembly_manifest,
    load_supervised_provider_discovery_loop_operator_record,
    run_supervised_provider_assembly_local_rehearsal,
    run_supervised_provider_discovery_handoff_rehearsal,
    run_supervised_provider_discovery_loop_operator_request,
    run_supervised_provider_discovery_operator_command_rehearsal,
    verify_supervised_provider_discovery_loop_operator_record,
    write_supervised_provider_discovery_loop_operator_request,
    write_supervised_provider_discovery_operator_request,
    write_supervised_provider_operator_request,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)


def test_discovery_loop_operator_completes_exact_discovered_list(
    tmp_path,
) -> None:
    request_path, output_root, finite_root = _composition_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    record = run_supervised_provider_discovery_loop_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert record.status == SupervisedProviderDiscoveryLoopStatus.COMPLETED
    assert record.finite_manifest_path is not None
    assert record.finite_loop_record_path is not None
    assert (finite_root / "loops").is_dir()
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()
    verify_supervised_provider_discovery_loop_operator_record(record)


def test_discovery_loop_operator_blocks_before_loop_when_discovery_blocks(
    tmp_path,
) -> None:
    request_path, _, finite_root = _composition_request(
        tmp_path,
        ("successful_assembly", "restart_reuse"),
        maximum_requests=1,
    )

    record = run_supervised_provider_discovery_loop_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert record.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED
    assert record.finite_manifest_path is None
    assert record.finite_loop_record_path is None
    assert not finite_root.exists()


def test_discovery_loop_operator_blocks_after_loop_block(tmp_path) -> None:
    request_path, _, finite_root = _composition_request(
        tmp_path,
        ("successful_assembly", "stale_target_rejected", "restart_reuse"),
        maximum_requests=3,
    )

    record = run_supervised_provider_discovery_loop_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert record.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED
    assert record.finite_manifest_path is not None
    assert record.finite_loop_record_path is not None
    assert "finite loop blocked" in record.reason
    assert not (
        finite_root.parent
        / "request-outputs"
        / "successful_assembly"
        / "operator-runs"
    ).exists()


def test_discovery_loop_operator_restart_returns_verified_record(
    tmp_path,
) -> None:
    request_path, output_root, _ = _composition_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    first = run_supervised_provider_discovery_loop_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    second = run_supervised_provider_discovery_loop_operator_request(
        request_path=request_path,
        clock=lambda: _now(),
    )

    assert second == first
    assert (
        load_supervised_provider_discovery_loop_operator_record(
            output_root / "operator-runs" / "composition-request.json"
        )
        == first
    )


def test_discovery_loop_operator_cli_runs_manual_composition(tmp_path) -> None:
    request_path, output_root, _ = _composition_request(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "supervised-provider-discover-finite",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code == 0
    assert "Status: completed" in result.output
    assert "Finite record:" in result.output
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()


def test_discovery_loop_operator_cli_has_no_operational_selectors() -> None:
    result = CliRunner().invoke(
        app, ["dry-run", "supervised-provider-discover-finite", "--help"]
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


def _composition_request(
    root: Path,
    scenarios: tuple[str, ...],
    maximum_requests: int = 2,
) -> tuple[Path, Path, Path]:
    now = _now()
    discovery_operator_request_path, finite_root = _discovery_operator_request(
        root, scenarios, maximum_requests, now
    )
    command_rehearsal_root = root / "discovery-operator-command-rehearsal"
    run_supervised_provider_discovery_operator_command_rehearsal(
        rehearsal_id="composition-command-rehearsal",
        output_root=command_rehearsal_root,
        quant_executable_path=Path(".venv/bin/quant"),
        evaluated_at=now,
    )
    command_rehearsal_path = (
        command_rehearsal_root
        / "reports"
        / "composition-command-rehearsal.json"
    )
    output_root = root / "composition-output"
    request = SupervisedProviderDiscoveryLoopOperatorRequest(
        request_id="composition-request",
        discovery_operator_request_path=str(discovery_operator_request_path),
        discovery_operator_request_sha256=_sha256(
            discovery_operator_request_path
        ),
        discovery_operator_rehearsal_report_path=str(command_rehearsal_path),
        discovery_operator_rehearsal_report_sha256=_sha256(
            command_rehearsal_path
        ),
        output_root=str(output_root),
        created_at=now,
        evidence_refs=("discovery-loop-operator:test",),
    )
    return (
        write_supervised_provider_discovery_loop_operator_request(
            request, root / "reviewed-composition"
        ),
        output_root,
        finite_root,
    )


def _discovery_operator_request(
    root: Path,
    scenarios: tuple[str, ...],
    maximum_requests: int,
    now: datetime,
) -> tuple[Path, Path]:
    rehearsal_root = root / "discovery-handoff-rehearsal"
    run_supervised_provider_discovery_handoff_rehearsal(
        rehearsal_id="composition-handoff",
        output_root=rehearsal_root,
        evaluated_at=now,
    )
    rehearsal_path = rehearsal_root / "reports" / "composition-handoff.json"
    reviewed, _ = _reviewed_requests(root, scenarios, now)
    output_root = root / "discovery-output"
    finite_root = root / "finite-output"
    request = SupervisedProviderDiscoveryOperatorRequest(
        request_id="discovery-request",
        discovery_policy=SupervisedProviderDiscoveryPolicy(
            discovery_id="composition-discovery",
            discovery_policy_version="supervised_provider_discovery_v1",
            request_directory=str(reviewed),
            maximum_requests=maximum_requests,
            finite_loop_id="composition-finite-loop",
            finite_output_root=str(finite_root),
            created_at=now,
            evidence_refs=("discovery-loop-operator:test",),
        ),
        output_root=str(output_root),
        discovery_rehearsal_report_path=str(rehearsal_path),
        discovery_rehearsal_report_sha256=_sha256(rehearsal_path),
        created_at=now,
        evidence_refs=("discovery-loop-operator:test",),
    )
    return (
        write_supervised_provider_discovery_operator_request(
            request, root / "reviewed-discovery"
        ),
        finite_root,
    )


def _reviewed_requests(
    root: Path,
    scenarios: tuple[str, ...],
    now: datetime,
) -> tuple[Path, tuple[SupervisedProviderOperatorRequest, ...]]:
    prerequisite_root = root / "assembly-prerequisite"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="composition-assembly",
        output_root=prerequisite_root,
        evaluated_at=now,
    )
    report_path = prerequisite_root / "reports" / "composition-assembly.json"
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
        request_id=f"{scenario}-composition-request",
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
        evidence_refs=("discovery-loop-operator:test",),
    )


def _now() -> datetime:
    return datetime.now(UTC)


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
