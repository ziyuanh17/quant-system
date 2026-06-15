"""Test no-network supervised autonomous dry-run service rehearsal evidence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.autonomous import (
    SupervisedDryRunCycleOutcome,
    SupervisedDryRunRehearsalReport,
    SupervisedDryRunRehearsalScenario,
    SupervisedDryRunServiceStatus,
)
from quant.workflows import (
    load_and_verify_supervised_autonomous_dry_run_rehearsal,
    run_supervised_autonomous_dry_run_local_rehearsal,
)


def test_supervised_rehearsal_persists_complete_passing_evidence(
    tmp_path,
) -> None:
    report = run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        SupervisedDryRunRehearsalScenario
    )
    assert not report.prohibited_artifact_paths
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.HEALTHY_CONTINUATION
    ).cycle_outcomes == (
        SupervisedDryRunCycleOutcome.SUCCEEDED,
        SupervisedDryRunCycleOutcome.SUCCEEDED,
    )
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.DEGRADED_HEALTH_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.HEALTH_STOP,)
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.FAILED_HEALTH_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.HEALTH_STOP,)
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.EXPLICIT_SHUTDOWN_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.SHUTDOWN_STOP,)
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.BLOCKED_RUN_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.BLOCKED,)
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.PROVIDER_ERROR_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.ERROR_STOP,)
    assert _scenario(
        report, SupervisedDryRunRehearsalScenario.RUNTIME_BOUND_STOP
    ).cycle_outcomes == (SupervisedDryRunCycleOutcome.RUNTIME_STOP,)
    assert (
        _scenario(
            report, SupervisedDryRunRehearsalScenario.RESTART_CONTINUATION
        ).service_status
        == SupervisedDryRunServiceStatus.COMPLETED
    )
    assert (
        load_and_verify_supervised_autonomous_dry_run_rehearsal(
            tmp_path / "reports" / "supervised-rehearsal-1.json"
        )
        == report
    )


def test_supervised_rehearsal_restart_returns_verified_report(tmp_path) -> None:
    first = run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    second = run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_supervised_rehearsal_detects_missing_cycle_evidence(tmp_path) -> None:
    report = run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    Path(report.scenarios[0].cycle_event_paths[0]).unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        load_and_verify_supervised_autonomous_dry_run_rehearsal(
            tmp_path / "reports" / "supervised-rehearsal-1.json"
        )


def test_supervised_rehearsal_detects_changed_service_record(tmp_path) -> None:
    report = run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    path = Path(report.scenarios[0].service_record_path)
    path.write_text(path.read_text().replace('"completed"', '"stopped"', 1))

    with pytest.raises(ValueError, match="does not match report"):
        load_and_verify_supervised_autonomous_dry_run_rehearsal(
            tmp_path / "reports" / "supervised-rehearsal-1.json"
        )


def test_supervised_rehearsal_detects_prohibited_artifact(tmp_path) -> None:
    run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    (tmp_path / "scenarios" / "unexpected" / "orders").mkdir(parents=True)

    with pytest.raises(ValueError, match="prohibited evidence changed"):
        load_and_verify_supervised_autonomous_dry_run_rehearsal(
            tmp_path / "reports" / "supervised-rehearsal-1.json"
        )


def test_supervised_rehearsal_rejects_identity_reuse(tmp_path) -> None:
    run_supervised_autonomous_dry_run_local_rehearsal(
        rehearsal_id="supervised-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="already bound"):
        run_supervised_autonomous_dry_run_local_rehearsal(
            rehearsal_id="supervised-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now() + timedelta(seconds=1),
        )


def _scenario(
    report: SupervisedDryRunRehearsalReport,
    scenario: SupervisedDryRunRehearsalScenario,
):
    return next(item for item in report.scenarios if item.scenario == scenario)


def _now() -> datetime:
    return datetime(2026, 6, 15, 22, tzinfo=UTC)
