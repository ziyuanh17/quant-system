"""Test the evidence-verified actual-command provider operator rehearsal."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.operator import (
    SupervisedProviderOperatorRehearsalReport,
    SupervisedProviderOperatorRehearsalScenario,
)
from quant.workflows import (
    load_and_verify_supervised_provider_operator_rehearsal,
    run_supervised_provider_operator_command_rehearsal,
)


def test_operator_command_rehearsal_runs_every_scenario(tmp_path) -> None:
    report = _run(tmp_path)

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        SupervisedProviderOperatorRehearsalScenario
    )
    assert not report.prohibited_artifact_paths
    assert (
        load_and_verify_supervised_provider_operator_rehearsal(
            _report_path(tmp_path)
        )
        == report
    )


def test_operator_command_rehearsal_restart_returns_verified_report(
    tmp_path,
) -> None:
    now = _now()
    first = _run(tmp_path, now=now)
    second = _run(tmp_path, now=now)

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_operator_command_rehearsal_rejects_identity_reuse(tmp_path) -> None:
    _run(tmp_path)

    with pytest.raises(ValueError, match="bound to other inputs"):
        run_supervised_provider_operator_command_rehearsal(
            rehearsal_id="operator-command-rehearsal",
            output_root=tmp_path,
            quant_executable_path=_quant(),
            evaluated_at=_now() + timedelta(seconds=1),
        )


def test_operator_command_rehearsal_detects_changed_observation(
    tmp_path,
) -> None:
    report = _run(tmp_path)
    path = Path(report.scenarios[0].command_observation_paths[0])
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="evidence changed"):
        load_and_verify_supervised_provider_operator_rehearsal(
            _report_path(tmp_path)
        )


def test_operator_command_rehearsal_detects_changed_operator_record(
    tmp_path,
) -> None:
    report = _run(tmp_path)
    path = Path(report.scenarios[0].operator_record_paths[0])
    path.write_text(path.read_text() + " ")

    with pytest.raises(ValueError, match="evidence changed"):
        load_and_verify_supervised_provider_operator_rehearsal(
            _report_path(tmp_path)
        )


def test_operator_command_rehearsal_detects_prohibited_artifact(
    tmp_path,
) -> None:
    _run(tmp_path)
    (tmp_path / "scenarios" / "unexpected" / "orders").mkdir(parents=True)

    with pytest.raises(ValueError, match="prohibited evidence changed"):
        load_and_verify_supervised_provider_operator_rehearsal(
            _report_path(tmp_path)
        )


def test_operator_command_rehearsal_report_requires_every_scenario(
    tmp_path,
) -> None:
    report = _run(tmp_path)
    payload = report.model_dump(mode="json")
    payload["scenarios"] = payload["scenarios"][:-1]

    with pytest.raises(ValueError, match="must include every scenario"):
        SupervisedProviderOperatorRehearsalReport.model_validate(payload)


def _run(
    root: Path, *, now: datetime | None = None
) -> SupervisedProviderOperatorRehearsalReport:
    return run_supervised_provider_operator_command_rehearsal(
        rehearsal_id="operator-command-rehearsal",
        output_root=root,
        quant_executable_path=_quant(),
        evaluated_at=now or _now(),
    )


def _report_path(root: Path) -> Path:
    return root / "reports" / "operator-command-rehearsal.json"


def _quant() -> Path:
    return Path(".venv/bin/quant").resolve()


def _now() -> datetime:
    return datetime.now(UTC)
