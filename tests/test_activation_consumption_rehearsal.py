"""Test second-layer activation-consumption rehearsal behavior."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.activation import (
    ActivationConsumptionRehearsalReport,
    ActivationConsumptionRehearsalScenario,
    ActivationDecision,
)
from quant.workflows import run_activation_consumption_local_rehearsal


def test_activation_consumption_rehearsal_persists_complete_evidence(
    tmp_path,
) -> None:
    report = run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        ActivationConsumptionRehearsalScenario
    )
    assert all(item.passed for item in report.scenarios)
    assert _scenario(
        report, ActivationConsumptionRehearsalScenario.DRY_RUN_RESTART
    ).activation_decisions == (
        ActivationDecision.ALLOWED,
        ActivationDecision.ALLOWED,
    )
    assert _scenario(
        report,
        ActivationConsumptionRehearsalScenario.EXPIRED_AUTHORIZATION_BLOCK,
    ).activation_decisions == (ActivationDecision.BLOCKED,)
    assert _scenario(
        report,
        ActivationConsumptionRehearsalScenario.SCOPE_MISMATCH_BLOCK,
    ).workflow_paths == ()


def test_activation_consumption_rehearsal_restart_verifies_evidence(
    tmp_path,
) -> None:
    first = run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    second = run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_activation_consumption_rehearsal_detects_missing_evidence(
    tmp_path,
) -> None:
    report = run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    missing = Path(report.scenarios[0].consumption_paths[0])
    missing.unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        run_activation_consumption_local_rehearsal(
            rehearsal_id="activation-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def test_activation_consumption_rehearsal_detects_missing_base_report(
    tmp_path,
) -> None:
    report = run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    Path(report.base_rehearsal_report_path).unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        run_activation_consumption_local_rehearsal(
            rehearsal_id="activation-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def test_activation_consumption_rehearsal_rejects_identity_reuse(
    tmp_path,
) -> None:
    run_activation_consumption_local_rehearsal(
        rehearsal_id="activation-rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="already bound"):
        run_activation_consumption_local_rehearsal(
            rehearsal_id="activation-rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now() + timedelta(seconds=1),
        )


def _scenario(
    report: ActivationConsumptionRehearsalReport,
    scenario: ActivationConsumptionRehearsalScenario,
):
    return next(item for item in report.scenarios if item.scenario == scenario)


def _now() -> datetime:
    return datetime(2026, 6, 13, 15, tzinfo=UTC)
