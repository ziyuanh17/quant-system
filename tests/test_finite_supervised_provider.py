"""Test finite manually started fresh supervised-provider request lists."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    FiniteSupervisedProviderManifest,
    FiniteSupervisedProviderStatus,
    SupervisedProviderOperatorRequest,
)
from quant.workflows import (
    finite_supervised_provider_manifest_for_paths,
    load_finite_supervised_provider_record,
    load_supervised_provider_assembly_manifest,
    run_finite_supervised_provider_loop,
    run_supervised_provider_assembly_local_rehearsal,
    write_finite_supervised_provider_manifest,
    write_supervised_provider_operator_request,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)


def test_finite_provider_completes_exact_fresh_request_list(tmp_path) -> None:
    manifest_path, loop_root, requests = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    record = run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert record.status == FiniteSupervisedProviderStatus.COMPLETED
    assert record.completed_request_ids == tuple(
        item.request_id for item in requests
    )
    assert len(record.operator_record_paths) == 2
    assert not (loop_root / "orders").exists()
    assert not (loop_root / "fills").exists()
    assert not (loop_root / "semantic-paper").exists()
    assert not (loop_root / "alpaca").exists()


def test_finite_provider_stops_on_first_stale_request(tmp_path) -> None:
    manifest_path, loop_root, requests = _manifest(
        tmp_path,
        ("successful_assembly", "stale_target_rejected", "restart_reuse"),
    )

    record = run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert record.status == FiniteSupervisedProviderStatus.BLOCKED
    assert record.completed_request_ids == (requests[0].request_id,)
    assert record.blocked_request_id == requests[1].request_id
    assert "do not aggregate actively" in record.reason
    assert not (
        Path(requests[2].output_root)
        / "operator-runs"
        / f"{requests[2].request_id}.json"
    ).exists()
    assert not (loop_root / "orders").exists()


def test_finite_provider_restart_returns_verified_summary(tmp_path) -> None:
    manifest_path, loop_root, _ = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    first = run_finite_supervised_provider_loop(manifest_path=manifest_path)

    second = run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert second == first
    assert (
        load_finite_supervised_provider_record(
            loop_root / "loops" / "finite-provider-1.json"
        )
        == first
    )


def test_finite_provider_restart_detects_changed_operator_evidence(
    tmp_path,
) -> None:
    manifest_path, _, _ = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    record = run_finite_supervised_provider_loop(manifest_path=manifest_path)
    operator_path = Path(record.operator_record_paths[0])
    operator = SupervisedProviderOperatorRequest.model_validate_json(
        Path(_load_manifest_request_paths(manifest_path)[0]).read_text()
    )
    service_path = (
        Path(operator.output_root)
        / "supervisor"
        / "services"
        / operator.service_policy.service_id
        / "record.json"
    )
    service_path.write_text(service_path.read_text() + " ")

    with pytest.raises(ValueError, match="operator evidence changed"):
        run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert operator_path.is_file()


def test_finite_provider_rejects_changed_request_before_any_run(
    tmp_path,
) -> None:
    manifest_path, _, requests = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    path = Path(_load_manifest_request_paths(manifest_path)[1])
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="request hash does not match"):
        run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert all(
        not (Path(item.output_root) / "operator-runs").exists()
        for item in requests
    )


def test_finite_provider_rejects_changed_later_input_before_any_run(
    tmp_path,
) -> None:
    manifest_path, _, requests = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    path = Path(requests[1].assembly_manifest_path)
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="linked input hash does not match"):
        run_finite_supervised_provider_loop(manifest_path=manifest_path)

    assert all(
        not (Path(item.output_root) / "operator-runs").exists()
        for item in requests
    )


def test_finite_provider_rejects_duplicate_output_roots(tmp_path) -> None:
    manifest_path, _, requests = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    duplicate = requests[1].model_copy(
        update={
            "request_id": "duplicate-output-request",
            "output_root": requests[0].output_root,
        }
    )
    duplicate_path = write_supervised_provider_operator_request(
        duplicate, tmp_path / "duplicate-reviewed"
    )
    manifest = finite_supervised_provider_manifest_for_paths(
        loop_id="duplicate-output-loop",
        request_paths=(
            Path(_load_manifest_request_paths(manifest_path)[0]),
            duplicate_path,
        ),
        output_root=tmp_path / "duplicate-loop-output",
        created_at=datetime.now(UTC),
    )
    changed_manifest_path = write_finite_supervised_provider_manifest(
        manifest, tmp_path / "duplicate-manifests"
    )

    with pytest.raises(ValueError, match="output roots must be unique"):
        run_finite_supervised_provider_loop(manifest_path=changed_manifest_path)


def test_finite_provider_cli_runs_only_manifest_bounded_requests(
    tmp_path,
) -> None:
    manifest_path, loop_root, _ = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "supervised-provider-finite",
            "--manifest-path",
            str(manifest_path),
        ],
    )

    assert result.exit_code == 0
    assert "Status: completed" in result.output
    assert "Completed: 2/2" in result.output
    assert not (loop_root / "orders").exists()
    assert not (loop_root / "fills").exists()


def test_finite_provider_cli_has_no_unbounded_or_operational_selectors() -> (
    None
):
    result = CliRunner().invoke(
        app, ["dry-run", "supervised-provider-finite", "--help"]
    )

    assert result.exit_code == 0
    assert "--manifest-path" in result.output
    assert "--output-root" not in result.output
    assert "--iterations" not in result.output
    assert "--mode" not in result.output
    assert "broker" not in result.output.lower()
    assert "alpaca" not in result.output.lower()
    assert "paper" not in result.output.lower()
    assert "scheduler" not in result.output.lower()


def _manifest(
    root: Path,
    scenarios: tuple[str, ...],
) -> tuple[Path, Path, tuple[SupervisedProviderOperatorRequest, ...]]:
    now = datetime.now(UTC)
    prerequisite_root = root / "prerequisite"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="finite-provider-prerequisite",
        output_root=prerequisite_root,
        evaluated_at=now,
    )
    report_path = (
        prerequisite_root / "reports" / "finite-provider-prerequisite.json"
    )
    requests = tuple(
        _request(root, prerequisite_root, report_path, scenario, now)
        for scenario in scenarios
    )
    request_paths = tuple(
        write_supervised_provider_operator_request(request, root / "reviewed")
        for request in requests
    )
    loop_root = root / "finite-output"
    manifest = finite_supervised_provider_manifest_for_paths(
        loop_id="finite-provider-1",
        request_paths=request_paths,
        output_root=loop_root,
        created_at=now,
    )
    return (
        write_finite_supervised_provider_manifest(manifest, root / "manifests"),
        loop_root,
        requests,
    )


def test_finite_provider_rejects_overlapping_output_roots(tmp_path) -> None:
    manifest_path, _, requests = _manifest(
        tmp_path, ("successful_assembly", "restart_reuse")
    )
    nested = requests[1].model_copy(
        update={
            "request_id": "nested-output-request",
            "output_root": str(Path(requests[0].output_root) / "nested"),
        }
    )
    nested_path = write_supervised_provider_operator_request(
        nested, tmp_path / "nested-reviewed"
    )
    manifest = finite_supervised_provider_manifest_for_paths(
        loop_id="nested-output-loop",
        request_paths=(
            Path(_load_manifest_request_paths(manifest_path)[0]),
            nested_path,
        ),
        output_root=tmp_path / "nested-loop-output",
        created_at=datetime.now(UTC),
    )
    changed_manifest_path = write_finite_supervised_provider_manifest(
        manifest, tmp_path / "nested-manifests"
    )

    with pytest.raises(ValueError, match="output roots must not overlap"):
        run_finite_supervised_provider_loop(manifest_path=changed_manifest_path)


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
        request_id=f"{scenario}-finite-request",
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
        evidence_refs=("finite-provider:test",),
    )


def _load_manifest_request_paths(path: Path) -> tuple[str, ...]:
    return FiniteSupervisedProviderManifest.model_validate_json(
        path.read_text()
    ).request_paths


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()
