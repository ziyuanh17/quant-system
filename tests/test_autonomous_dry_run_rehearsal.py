"""Test no-network autonomous dry-run rehearsal evidence."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.autonomous import (
    AutonomousDryRunRehearsalReport,
    AutonomousDryRunRehearsalScenario,
    AutonomousDryRunStatus,
)
from quant.workflows import (
    load_and_verify_autonomous_dry_run_rehearsal,
    run_autonomous_dry_run_local_rehearsal,
)


def test_autonomous_rehearsal_persists_complete_passing_evidence(
    tmp_path,
) -> None:
    report = run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        AutonomousDryRunRehearsalScenario
    )
    assert _scenario(
        report, AutonomousDryRunRehearsalScenario.REPEATED_ALLOWED_RUNS
    ).run_statuses == (
        AutonomousDryRunStatus.SUCCEEDED,
        AutonomousDryRunStatus.SUCCEEDED,
    )
    assert _scenario(
        report, AutonomousDryRunRehearsalScenario.EXPIRED_AUTHORIZATION_BLOCK
    ).run_statuses == (AutonomousDryRunStatus.BLOCKED,)
    assert _scenario(
        report, AutonomousDryRunRehearsalScenario.HALT_AFTER_BLOCK
    ).run_statuses == (
        AutonomousDryRunStatus.BLOCKED,
        AutonomousDryRunStatus.BLOCKED,
    )
    assert load_and_verify_autonomous_dry_run_rehearsal(
        tmp_path / "reports" / "autonomous-rehearsal-1.json"
    ) == report


def test_autonomous_rehearsal_restart_returns_verified_report(tmp_path) -> None:
    first = run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    second = run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_autonomous_rehearsal_detects_missing_run_evidence(tmp_path) -> None:
    report = run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    Path(report.scenarios[0].run_paths[0]).unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        run_autonomous_dry_run_local_rehearsal(
            rehearsal_id="autonomous-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def test_autonomous_rehearsal_detects_changed_run_evidence(tmp_path) -> None:
    report = run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    path = Path(report.scenarios[0].run_paths[0])
    path.write_text(path.read_text().replace('"succeeded"', '"blocked"', 1))

    with pytest.raises(ValueError, match="does not match report"):
        load_and_verify_autonomous_dry_run_rehearsal(
            tmp_path / "reports" / "autonomous-rehearsal-1.json"
        )


def test_autonomous_rehearsal_rejects_identity_reuse(tmp_path) -> None:
    run_autonomous_dry_run_local_rehearsal(
        rehearsal_id="autonomous-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="already bound"):
        run_autonomous_dry_run_local_rehearsal(
            rehearsal_id="autonomous-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now() + timedelta(seconds=1),
        )


def _scenario(
    report: AutonomousDryRunRehearsalReport,
    scenario: AutonomousDryRunRehearsalScenario,
):
    return next(item for item in report.scenarios if item.scenario == scenario)


def _now() -> datetime:
    return datetime(2026, 6, 15, 18, tzinfo=UTC)
