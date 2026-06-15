"""Test no-network local provider-assembly rehearsal evidence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.autonomous import (
    SupervisedProviderAssemblyRehearsalOutcome,
    SupervisedProviderAssemblyRehearsalReport,
    SupervisedProviderAssemblyRehearsalScenario,
)
from quant.workflows import (
    load_and_verify_supervised_provider_assembly_rehearsal,
    run_supervised_provider_assembly_local_rehearsal,
)


def test_provider_assembly_rehearsal_persists_complete_evidence(
    tmp_path,
) -> None:
    report = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        SupervisedProviderAssemblyRehearsalScenario
    )
    assert not report.prohibited_artifact_paths
    assert (
        _scenario(
            report,
            SupervisedProviderAssemblyRehearsalScenario.SUCCESSFUL_ASSEMBLY,
        ).outcome
        == SupervisedProviderAssemblyRehearsalOutcome.ASSEMBLED
    )
    assert (
        _scenario(
            report,
            SupervisedProviderAssemblyRehearsalScenario.CHANGED_INPUT_REJECTED,
        ).outcome
        == SupervisedProviderAssemblyRehearsalOutcome.REJECTED
    )
    assert (
        _scenario(
            report,
            SupervisedProviderAssemblyRehearsalScenario.PROVIDER_TO_SUPERVISOR,
        ).outcome
        == SupervisedProviderAssemblyRehearsalOutcome.SUPERVISOR_COMPLETED
    )
    assert (
        load_and_verify_supervised_provider_assembly_rehearsal(
            tmp_path / "reports" / "provider-assembly-rehearsal-1.json"
        )
        == report
    )


def test_provider_assembly_rehearsal_restart_returns_verified_report(
    tmp_path,
) -> None:
    first = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    second = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_provider_assembly_rehearsal_detects_missing_evidence(tmp_path) -> None:
    report = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    Path(report.scenarios[0].evidence_paths[0]).unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        load_and_verify_supervised_provider_assembly_rehearsal(
            tmp_path / "reports" / "provider-assembly-rehearsal-1.json"
        )


def test_provider_assembly_rehearsal_detects_changed_valid_output(
    tmp_path,
) -> None:
    report = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    record_path = Path(report.scenarios[0].assembly_record_paths[0])
    record = record_path.read_text()
    output_path = next(
        Path(path)
        for path in report.scenarios[0].evidence_paths
        if "health-snapshots" in path
    )
    output_path.write_text(
        output_path.read_text().replace('"healthy"', '"failed"', 1)
    )
    assert record_path.read_text() == record

    with pytest.raises(ValueError, match="output does not match record"):
        load_and_verify_supervised_provider_assembly_rehearsal(
            tmp_path / "reports" / "provider-assembly-rehearsal-1.json"
        )


def test_provider_assembly_rehearsal_detects_prohibited_artifact(
    tmp_path,
) -> None:
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    (tmp_path / "scenarios" / "unexpected" / "orders").mkdir(parents=True)

    with pytest.raises(ValueError, match="prohibited evidence changed"):
        load_and_verify_supervised_provider_assembly_rehearsal(
            tmp_path / "reports" / "provider-assembly-rehearsal-1.json"
        )


def test_provider_assembly_rehearsal_rejects_identity_reuse(tmp_path) -> None:
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="bound to other inputs"):
        run_supervised_provider_assembly_local_rehearsal(
            rehearsal_id="provider-assembly-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now() + timedelta(seconds=1),
        )


def test_provider_assembly_rehearsal_report_requires_every_scenario(
    tmp_path,
) -> None:
    report = run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id="provider-assembly-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    payload = report.model_dump(mode="json")
    payload["scenarios"] = payload["scenarios"][:-1]

    with pytest.raises(ValueError, match="must include every scenario"):
        SupervisedProviderAssemblyRehearsalReport.model_validate(payload)


def _scenario(
    report: SupervisedProviderAssemblyRehearsalReport,
    scenario: SupervisedProviderAssemblyRehearsalScenario,
):
    return next(item for item in report.scenarios if item.scenario == scenario)


def _now() -> datetime:
    return datetime(2026, 6, 16, 1, tzinfo=UTC)
