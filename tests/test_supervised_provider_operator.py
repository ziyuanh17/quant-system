"""Test the manually started supervised-provider dry-run boundary."""

from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

import pytest
from typer.testing import CliRunner

from quant.cli import app
from quant.models.autonomous import (
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
)
from quant.models.operator import SupervisedProviderOperatorRequest
from quant.workflows import (
    load_supervised_provider_assembly_manifest,
    load_supervised_provider_assembly_record,
    load_supervised_provider_operator_record,
    run_supervised_provider_assembly_local_rehearsal,
    run_supervised_provider_operator_request,
    write_supervised_provider_operator_request,
)
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)


def test_operator_assembles_and_completes_one_supervised_cycle(
    tmp_path,
) -> None:
    request_path, output_root, now = _request_path(tmp_path)

    record = run_supervised_provider_operator_request(
        request_path=request_path,
        clock=_Clock(now, now, now),
    )

    assert record.service_status == SupervisedDryRunServiceStatus.COMPLETED
    assert Path(record.assembly_record_path).is_file()
    assert Path(record.service_record_path).is_file()
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()
    assert not (output_root / "semantic-paper").exists()
    assert not (output_root / "alpaca").exists()


def test_operator_restart_returns_verified_record(tmp_path) -> None:
    request_path, output_root, now = _request_path(tmp_path)
    first = run_supervised_provider_operator_request(
        request_path=request_path,
        clock=_Clock(now, now, now),
    )

    second = run_supervised_provider_operator_request(
        request_path=request_path,
        clock=_Clock(),
    )

    assert second == first
    assert (
        load_supervised_provider_operator_record(
            output_root / "operator-runs" / "operator-request-1.json"
        )
        == first
    )


def test_operator_restart_detects_changed_service_record(tmp_path) -> None:
    request_path, _, now = _request_path(tmp_path)
    record = run_supervised_provider_operator_request(
        request_path=request_path,
        clock=_Clock(now, now, now),
    )
    path = Path(record.service_record_path)
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="operator evidence changed"):
        run_supervised_provider_operator_request(request_path=request_path)


def test_operator_restart_detects_changed_assembly_output(tmp_path) -> None:
    request_path, _, now = _request_path(tmp_path)
    record = run_supervised_provider_operator_request(
        request_path=request_path,
        clock=_Clock(now, now, now),
    )
    assembly = load_supervised_provider_assembly_record(
        Path(record.assembly_record_path)
    )
    path = Path(assembly.health_snapshot_path)
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="operator evidence changed"):
        run_supervised_provider_operator_request(request_path=request_path)


def test_operator_rejects_changed_manifest_before_assembly(tmp_path) -> None:
    request_path, output_root, _ = _request_path(tmp_path)
    request = SupervisedProviderOperatorRequest.model_validate_json(
        request_path.read_text()
    )
    path = Path(request.assembly_manifest_path)
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="input hash does not match"):
        run_supervised_provider_operator_request(request_path=request_path)

    assert not (output_root / "assembly").exists()
    assert not (output_root / "supervisor").exists()


def test_operator_requires_single_zero_interval_cycle(tmp_path) -> None:
    request_path, output_root, _ = _request_path(tmp_path, maximum_cycles=2)

    with pytest.raises(ValueError, match="exactly one cycle"):
        run_supervised_provider_operator_request(request_path=request_path)

    assert not (output_root / "assembly").exists()
    assert not (output_root / "supervisor").exists()


def test_operator_rejects_wrong_authorization_before_assembly(tmp_path) -> None:
    request_path, output_root, _ = _request_path(tmp_path)
    original = SupervisedProviderOperatorRequest.model_validate_json(
        request_path.read_text()
    )
    request = original.model_copy(
        update={
            "request_id": "operator-request-wrong-authorization",
            "service_policy": original.service_policy.model_copy(
                update={"authorization_id": "other-authorization"}
            ),
        }
    )
    changed_path = write_supervised_provider_operator_request(
        request, tmp_path / "reviewed"
    )

    with pytest.raises(ValueError, match="another authorization"):
        run_supervised_provider_operator_request(request_path=changed_path)

    assert not (output_root / "assembly").exists()
    assert not (output_root / "supervisor").exists()


def test_operator_cli_runs_only_reviewed_request(tmp_path) -> None:
    request_path, output_root, _ = _request_path(tmp_path)

    result = CliRunner().invoke(
        app,
        [
            "dry-run",
            "supervised-provider",
            "--request-path",
            str(request_path),
        ],
    )

    assert result.exit_code == 0
    assert "Status: completed" in result.output
    assert not (output_root / "orders").exists()
    assert not (output_root / "fills").exists()


def test_operator_cli_has_no_operational_selectors() -> None:
    result = CliRunner().invoke(
        app, ["dry-run", "supervised-provider", "--help"]
    )

    assert result.exit_code == 0
    assert "--request-path" in result.output
    assert "--output-root" not in result.output
    assert "--mode" not in result.output
    assert "broker" not in result.output.lower()
    assert "alpaca" not in result.output.lower()
    assert "paper" not in result.output.lower()
    assert "scheduler" not in result.output.lower()


def _request_path(
    root: Path,
    *,
    maximum_cycles: int = 1,
) -> tuple[Path, Path, datetime]:
    now = datetime.now(UTC)
    rehearsal_root = root / "rehearsal"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal",
        output_root=rehearsal_root,
        evaluated_at=now,
    )
    report_path = (
        rehearsal_root / "reports" / "provider-assembly-rehearsal.json"
    )
    manifest_path = (
        rehearsal_root
        / "scenarios"
        / "successful_assembly"
        / "output"
        / "assemblies"
        / "successful_assembly-assembly"
        / "manifest.json"
    )
    manifest = load_supervised_provider_assembly_manifest(manifest_path)
    authorization = load_autonomous_dry_run_authorization(
        Path(manifest.authorization_path)
    )
    output_root = root / "operator-output"
    request = SupervisedProviderOperatorRequest(
        request_id="operator-request-1",
        assembly_manifest_path=str(manifest_path),
        assembly_manifest_sha256=_sha256(manifest_path),
        assembly_rehearsal_report_path=str(report_path),
        assembly_rehearsal_report_sha256=_sha256(report_path),
        service_policy=SupervisedDryRunServicePolicy(
            service_id=manifest.service_id,
            policy_version="bounded_supervised_dry_run_v1",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            maximum_cycles=maximum_cycles,
            interval_seconds=0,
            maximum_runtime_seconds=60,
            created_at=now,
        ),
        output_root=str(output_root),
        created_at=now,
        evidence_refs=("reviewed:provider-assembly-rehearsal",),
    )
    request_path = write_supervised_provider_operator_request(
        request, root / "reviewed"
    )
    return request_path, output_root, now


def _sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)
