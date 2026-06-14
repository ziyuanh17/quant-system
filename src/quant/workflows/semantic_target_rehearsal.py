import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path

from pydantic import BaseModel

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.execution.reconciliation import reconcile_live_state
from quant.execution.semantic_paper import SemanticPaperBrokerClient
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveReconciliationDifference,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionDryRunStatus,
    ExecutionLifecyclePolicy,
    ExecutionPlanStatus,
)
from quant.models.targets import (
    ContributorSet,
    ContributorSpec,
    ResearchRiskPolicy,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
    TargetDeclaredStatus,
    TargetUnit,
)
from quant.models.workflow import (
    SemanticTargetRehearsalReport,
    SemanticTargetRehearsalScenario,
    SemanticTargetRehearsalScenarioResult,
    SemanticTargetWorkflowRecord,
    SemanticTargetWorkflowStatus,
)
from quant.operations import FileLock
from quant.workflows.semantic_targets import (
    SemanticTargetWorkflowResult,
    run_semantic_target_dry_run_workflow,
    run_semantic_target_paper_workflow,
)

SEMANTIC_TARGET_REHEARSAL_POLICY = "semantic_target_local_rehearsal_v2"


def run_semantic_target_local_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> SemanticTargetRehearsalReport:
    """Run deterministic no-network scenarios and persist proof."""
    _require_safe_id(rehearsal_id)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"semantic-target-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = SemanticTargetRehearsalReport.model_validate_json(
                report_path.read_text()
            )
            if (
                report.evaluated_at != evaluated_at
                or report.rehearsal_policy_version
                != SEMANTIC_TARGET_REHEARSAL_POLICY
            ):
                raise ValueError(
                    "rehearsal ID is already bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        scenarios = (
            _dry_run_eligible(output_root, evaluated_at),
            _dry_run_restart(output_root, evaluated_at),
            _stale_target_block(output_root, evaluated_at),
            _working_order_block(output_root, evaluated_at),
            _risk_rejection(output_root, evaluated_at),
            _fractional_target_block(output_root, evaluated_at),
            _local_paper_restart(output_root, evaluated_at),
            _reconciliation_failure(output_root, evaluated_at),
        )
        passed = all(item.passed for item in scenarios)
        report = SemanticTargetRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            reason=(
                "all controlled semantic-target rehearsal scenarios passed"
                if passed
                else "one or more controlled rehearsal scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def _dry_run_eligible(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    result = _run_dry("dry-run-eligible", root, evaluated_at)
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.DRY_RUN_ELIGIBLE,
        results=(result,),
        passed=(
            result.record.status
            == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
            and result.record.dry_run_status
            == ExecutionDryRunStatus.WOULD_SUBMIT
        ),
        root=root,
        reason="eligible dry-run produced would-submit evidence",
    )


def _dry_run_restart(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    first = _run_dry("dry-run-restart", root, evaluated_at)
    second = _run_dry("dry-run-restart", root, evaluated_at)
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.DRY_RUN_RESTART,
        results=(first, second),
        passed=first == second,
        root=root,
        reason="repeated dry-run returned the same durable result",
    )


def _stale_target_block(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    result = _run_dry(
        "stale-target-block",
        root,
        evaluated_at,
        generated_at=evaluated_at - timedelta(hours=2),
        valid_until=evaluated_at + timedelta(hours=1),
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.STALE_TARGET_BLOCK,
        results=(result,),
        passed=(
            result.record.status
            == SemanticTargetWorkflowStatus.PORTFOLIO_BLOCKED
            and result.record.execution_plan_id is None
        ),
        root=root,
        reason="stale strategy target blocked before execution planning",
    )


def _working_order_block(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    result = _run_dry(
        "working-order-block",
        root,
        evaluated_at,
        open_order_ids=("working-order-1",),
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.WORKING_ORDER_BLOCK,
        results=(result,),
        passed=(
            result.record.status
            == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
            and result.record.dry_run_status == ExecutionDryRunStatus.BLOCKED
        ),
        root=root,
        reason="working order produced durable blocked dry-run evidence",
    )


def _risk_rejection(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    result = _run_dry(
        "risk-rejection",
        root,
        evaluated_at,
        risk_limit=Decimal("1"),
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.RISK_REJECTION,
        results=(result,),
        passed=(
            result.record.status == SemanticTargetWorkflowStatus.RISK_REJECTED
            and result.record.execution_plan_id is None
        ),
        root=root,
        reason="risk rejection stopped before execution planning",
    )


def _fractional_target_block(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    result = _run_dry(
        "fractional-target-block",
        root,
        evaluated_at,
        target_value=Decimal("1.5"),
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.FRACTIONAL_TARGET_BLOCK,
        results=(result,),
        passed=(
            result.record.status
            == SemanticTargetWorkflowStatus.OPERATIONALLY_BLOCKED
            and result.risk_target.approved_target_value == Decimal("1.5")
            and result.record.execution_plan_id is None
        ),
        root=root,
        reason="fractional research target was preserved and not rounded",
    )


def _local_paper_restart(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    first = _run_paper("local-paper-restart", root, evaluated_at)
    second = _run_paper("local-paper-restart", root, evaluated_at)
    scenario_root = root / "scenarios" / "local-paper-restart"
    order_count = len(
        tuple((scenario_root / "semantic-paper" / "orders").glob("*.json"))
    )
    fill_count = len(
        tuple((scenario_root / "semantic-paper" / "fills").glob("*.json"))
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.LOCAL_PAPER_RESTART,
        results=(first, second),
        passed=(
            first == second
            and first.record.execution_status == ExecutionPlanStatus.SATISFIED
            and order_count == 1
            and fill_count == 1
        ),
        root=root,
        reason="local paper restart preserved one satisfied order and fill",
    )


def _reconciliation_failure(
    root: Path, evaluated_at: datetime
) -> SemanticTargetRehearsalScenarioResult:
    first = _run_paper(
        "reconciliation-failure",
        root,
        evaluated_at,
        reconciliation_runner=_inject_reconciliation_failure,
        reconciliation_runner_id="inject_reconciliation_failure_v1",
    )
    second = _run_paper(
        "reconciliation-failure",
        root,
        evaluated_at,
        reconciliation_runner=_inject_reconciliation_failure,
        reconciliation_runner_id="inject_reconciliation_failure_v1",
    )
    scenario_root = root / "scenarios" / "reconciliation-failure"
    reconciliation_dir = (
        scenario_root / "semantic-paper" / "reconciliations"
    )
    reports = tuple(
        LiveReconciliationReport.model_validate_json(path.read_text())
        for path in reconciliation_dir.rglob("*.json")
    )
    order_count = len(
        tuple((scenario_root / "semantic-paper" / "orders").glob("*.json"))
    )
    fill_count = len(
        tuple((scenario_root / "semantic-paper" / "fills").glob("*.json"))
    )
    return _scenario_result(
        scenario=SemanticTargetRehearsalScenario.RECONCILIATION_FAILURE,
        results=(first, second),
        passed=(
            first == second
            and first.record.execution_status == ExecutionPlanStatus.FILLED
            and first.record.reconciliation_report_id is not None
            and len(reports) == 1
            and not reports[0].passed
            and order_count == 1
            and fill_count == 1
        ),
        root=root,
        supporting_evidence_paths=tuple(
            str(path)
            for path in reconciliation_dir.rglob("*.json")
        ),
        reason=(
            "failed reconciliation prevented satisfaction across restart "
            "without duplicating the order or fill"
        ),
    )


def _run_dry(
    scenario_id: str,
    root: Path,
    evaluated_at: datetime,
    *,
    target_value: Decimal = Decimal("2"),
    generated_at: datetime | None = None,
    valid_until: datetime | None = None,
    risk_limit: Decimal = Decimal("10"),
    open_order_ids: tuple[str, ...] = (),
) -> SemanticTargetWorkflowResult:
    scenario_root = root / "scenarios" / scenario_id
    decision, evaluation = _target_inputs(
        scenario_id,
        evaluated_at,
        target_value=target_value,
        generated_at=generated_at,
        valid_until=valid_until,
    )
    return run_semantic_target_dry_run_workflow(
        orchestration_id=scenario_id,
        contributor_set=_contributor_set(scenario_id),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=_risk_policy(risk_limit),
        portfolio_target_id=f"portfolio-{scenario_id}",
        portfolio_target_revision=1,
        risk_target_id=f"risk-{scenario_id}",
        risk_target_revision=1,
        account=_account(evaluated_at, open_order_ids=open_order_ids),
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        output_root=scenario_root,
        evaluated_at=evaluated_at,
    )


def _run_paper(
    scenario_id: str,
    root: Path,
    evaluated_at: datetime,
    *,
    reconciliation_runner=reconcile_live_state,
    reconciliation_runner_id: str = "reconcile_live_state_v1",
) -> SemanticTargetWorkflowResult:
    scenario_root = root / "scenarios" / scenario_id
    decision, evaluation = _target_inputs(scenario_id, evaluated_at)
    return run_semantic_target_paper_workflow(
        orchestration_id=scenario_id,
        contributor_set=_contributor_set(scenario_id),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=_risk_policy(Decimal("10")),
        portfolio_target_id=f"portfolio-{scenario_id}",
        portfolio_target_revision=1,
        risk_target_id=f"risk-{scenario_id}",
        risk_target_revision=1,
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.PAPER,
            allowed=True,
        ),
        output_root=scenario_root,
        initial_cash=1_000,
        evaluated_at=evaluated_at,
        reconciliation_runner=reconciliation_runner,
        reconciliation_runner_id=reconciliation_runner_id,
    )


def _target_inputs(
    scenario_id: str,
    evaluated_at: datetime,
    *,
    target_value: Decimal = Decimal("2"),
    generated_at: datetime | None = None,
    valid_until: datetime | None = None,
) -> tuple[StrategyTargetDecision, StrategyEvaluation]:
    generated = generated_at or evaluated_at
    decision_id = f"decision-{scenario_id}"
    decision = StrategyTargetDecision(
        decision_id=decision_id,
        revision=1,
        strategy_id="rehearsal-strategy",
        strategy_version="1",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target_value,
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"synthetic-{scenario_id}",
        generated_at=generated,
        effective_at=generated,
        valid_until=valid_until or evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled no-network rehearsal target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"evaluation-{scenario_id}",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision_id,
        reason="controlled no-network rehearsal evaluation",
    )
    return decision, evaluation


def _contributor_set(scenario_id: str) -> ContributorSet:
    return ContributorSet(
        contributor_set_id=f"contributors-{scenario_id}",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(
                strategy_id="rehearsal-strategy",
                strategy_version="1",
            ),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled no-network rehearsal ownership",
    )


def _risk_policy(limit: Decimal) -> ResearchRiskPolicy:
    return ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=limit,
    )


def _execution_policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _account(
    evaluated_at: datetime,
    *,
    open_order_ids: tuple[str, ...] = (),
) -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        id=f"rehearsal-account-{len(open_order_ids)}",
        broker_name="local-rehearsal",
        account_id="local-rehearsal-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        open_order_ids=open_order_ids,
        captured_at=evaluated_at,
    )


def _inject_reconciliation_failure(
    *,
    client: SemanticPaperBrokerClient,
    order_records_dir: Path,
    fill_records_dir: Path,
    snapshot_records_dir: Path,
) -> LiveReconciliationReport:
    report = reconcile_live_state(
        client=client,
        order_records_dir=order_records_dir,
        fill_records_dir=fill_records_dir,
        snapshot_records_dir=snapshot_records_dir,
    )
    return report.model_copy(
        update={
            "status": LiveReconciliationStatus.FAILED,
            "differences": report.differences
            + (
                LiveReconciliationDifference(
                    field="rehearsal.injected_failure",
                    local_value="expected-pass",
                    broker_value="forced-failure",
                    message="deterministic reconciliation failure injection",
                ),
            ),
        }
    )


def _scenario_result(
    *,
    scenario: SemanticTargetRehearsalScenario,
    results: tuple[SemanticTargetWorkflowResult, ...],
    passed: bool,
    root: Path,
    reason: str,
    supporting_evidence_paths: tuple[str, ...] = (),
) -> SemanticTargetRehearsalScenarioResult:
    records = tuple(item.record for item in results)
    return SemanticTargetRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        orchestration_ids=tuple(item.orchestration_id for item in records),
        workflow_statuses=tuple(item.status for item in records),
        execution_statuses=tuple(item.execution_status for item in records),
        dry_run_statuses=tuple(item.dry_run_status for item in records),
        evidence_paths=tuple(_record_path(root, item) for item in records),
        supporting_evidence_paths=supporting_evidence_paths,
        reason=reason,
    )


def _record_path(root: Path, record: SemanticTargetWorkflowRecord) -> str:
    return str(
        root
        / "scenarios"
        / record.orchestration_id
        / "orchestrations"
        / f"{record.orchestration_id}.json"
    )


def _verify_report_evidence(report: SemanticTargetRehearsalReport) -> None:
    for scenario in report.scenarios:
        for path_value in scenario.supporting_evidence_paths:
            path = Path(path_value)
            if not path.is_file():
                raise ValueError(f"rehearsal evidence is missing: {path}")
        for index, path_value in enumerate(scenario.evidence_paths):
            path = Path(path_value)
            if not path.is_file():
                raise ValueError(f"rehearsal evidence is missing: {path}")
            record = SemanticTargetWorkflowRecord.model_validate_json(
                path.read_text()
            )
            if (
                record.orchestration_id != scenario.orchestration_ids[index]
                or record.status != scenario.workflow_statuses[index]
                or record.execution_status != scenario.execution_statuses[index]
                or record.dry_run_status != scenario.dry_run_statuses[index]
            ):
                raise ValueError(
                    f"rehearsal evidence does not match report: {path}"
                )


def _write_model_exclusive(path: Path, model: BaseModel) -> None:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _require_safe_id(value: str) -> None:
    if not value or value in {".", ".."} or "/" in value or "\\" in value:
        raise ValueError("rehearsal ID must be a safe path component")
