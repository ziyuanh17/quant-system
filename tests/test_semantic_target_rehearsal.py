from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionPlanStatus,
)
from quant.models.workflow import (
    SemanticTargetRehearsalReport,
    SemanticTargetRehearsalScenario,
    SemanticTargetWorkflowStatus,
)
from quant.workflows import run_semantic_target_local_rehearsal


def test_local_rehearsal_persists_complete_passing_evidence(tmp_path) -> None:
    report = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert report.passed
    assert tuple(item.scenario for item in report.scenarios) == tuple(
        SemanticTargetRehearsalScenario
    )
    assert all(item.passed for item in report.scenarios)
    assert (
        _scenario(report, SemanticTargetRehearsalScenario.DRY_RUN_ELIGIBLE)
        .dry_run_statuses
        == (ExecutionDryRunStatus.WOULD_SUBMIT,)
    )
    assert (
        _scenario(report, SemanticTargetRehearsalScenario.STALE_TARGET_BLOCK)
        .workflow_statuses
        == (SemanticTargetWorkflowStatus.PORTFOLIO_BLOCKED,)
    )
    assert (
        _scenario(report, SemanticTargetRehearsalScenario.WORKING_ORDER_BLOCK)
        .dry_run_statuses
        == (ExecutionDryRunStatus.BLOCKED,)
    )
    assert (
        _scenario(report, SemanticTargetRehearsalScenario.LOCAL_PAPER_RESTART)
        .execution_statuses
        == (
            ExecutionPlanStatus.SATISFIED,
            ExecutionPlanStatus.SATISFIED,
        )
    )
    assert (
        _scenario(
            report,
            SemanticTargetRehearsalScenario.RECONCILIATION_FAILURE,
        ).execution_statuses
        == (
            ExecutionPlanStatus.FILLED,
            ExecutionPlanStatus.FILLED,
        )
    )
    assert all(
        path.exists()
        for item in report.scenarios
        for path in map(Path, item.evidence_paths)
    )


def test_local_rehearsal_restart_returns_verified_report(tmp_path) -> None:
    first = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    second = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    assert second == first
    assert len(tuple((tmp_path / "reports").glob("*.json"))) == 1


def test_local_rehearsal_rejects_identity_reuse(tmp_path) -> None:
    run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )

    with pytest.raises(ValueError, match="already bound"):
        run_semantic_target_local_rehearsal(
            rehearsal_id="rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now() + timedelta(seconds=1),
        )


def test_local_rehearsal_detects_missing_evidence(tmp_path) -> None:
    report = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    missing = next(
        Path(path) for item in report.scenarios for path in item.evidence_paths
    )
    missing.unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        run_semantic_target_local_rehearsal(
            rehearsal_id="rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def test_local_rehearsal_detects_missing_failed_reconciliation(
    tmp_path,
) -> None:
    report = run_semantic_target_local_rehearsal(
        rehearsal_id="rehearsal-1",
        output_root=tmp_path,
        evaluated_at=_now(),
    )
    scenario = _scenario(
        report,
        SemanticTargetRehearsalScenario.RECONCILIATION_FAILURE,
    )
    assert len(scenario.supporting_evidence_paths) == 1
    Path(scenario.supporting_evidence_paths[0]).unlink()

    with pytest.raises(ValueError, match="evidence is missing"):
        run_semantic_target_local_rehearsal(
            rehearsal_id="rehearsal-1",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def test_local_rehearsal_rejects_unsafe_id(tmp_path) -> None:
    with pytest.raises(ValueError, match="safe path component"):
        run_semantic_target_local_rehearsal(
            rehearsal_id="../unsafe",
            output_root=tmp_path,
            evaluated_at=_now(),
        )


def _scenario(
    report: SemanticTargetRehearsalReport,
    scenario: SemanticTargetRehearsalScenario,
):
    return next(item for item in report.scenarios if item.scenario == scenario)


def _now() -> datetime:
    return datetime(2026, 6, 13, 15, tzinfo=UTC)
