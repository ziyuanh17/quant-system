"""Run second-layer no-network activation-consumption rehearsals."""

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
from quant.models.activation import (
    ActivationConsumptionRehearsalReport,
    ActivationConsumptionRehearsalScenario,
    ActivationConsumptionRehearsalScenarioResult,
    ActivationDecision,
    SemanticTargetActivationAuthorization,
    SemanticTargetActivationConsumption,
    SemanticTargetActivationEvaluation,
    SemanticTargetActivationScope,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
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
    SemanticTargetWorkflowRecord,
    SemanticTargetWorkflowStatus,
)
from quant.operations import FileLock
from quant.workflows.activated_semantic_targets import (
    ActivatedSemanticTargetWorkflowResult,
    run_activated_semantic_target_dry_run_workflow,
    run_activated_semantic_target_paper_workflow,
)
from quant.workflows.semantic_target_activation import (
    SEMANTIC_TARGET_ORCHESTRATION_POLICY,
    rehearsal_report_sha256,
)
from quant.workflows.semantic_target_rehearsal import (
    SEMANTIC_TARGET_REHEARSAL_POLICY,
    load_and_verify_semantic_target_rehearsal,
    run_semantic_target_local_rehearsal,
)

ACTIVATION_CONSUMPTION_REHEARSAL_POLICY = (
    "activation_consumption_local_rehearsal_v1"
)


def run_activation_consumption_local_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> ActivationConsumptionRehearsalReport:
    """Run consumption scenarios against a verified base rehearsal."""
    _require_safe_id(rehearsal_id)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"activation-consumption-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = ActivationConsumptionRehearsalReport.model_validate_json(
                report_path.read_text()
            )
            if (
                report.evaluated_at != evaluated_at
                or report.rehearsal_policy_version
                != ACTIVATION_CONSUMPTION_REHEARSAL_POLICY
            ):
                raise ValueError(
                    "activation rehearsal ID is already bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        base_root = output_root / "base-rehearsal"
        base_report = run_semantic_target_local_rehearsal(
            rehearsal_id=f"{rehearsal_id}-base",
            output_root=base_root,
            evaluated_at=evaluated_at,
        )
        base_path = base_root / "reports" / f"{base_report.rehearsal_id}.json"
        scenarios = (
            _dry_run_restart(output_root, base_path, evaluated_at),
            _local_paper_restart(output_root, base_path, evaluated_at),
            _expired_authorization_block(output_root, base_path, evaluated_at),
            _scope_mismatch_block(output_root, base_path, evaluated_at),
            _single_consumption_enforcement(
                output_root, base_path, evaluated_at
            ),
        )
        passed = all(item.passed for item in scenarios)
        report = ActivationConsumptionRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=ACTIVATION_CONSUMPTION_REHEARSAL_POLICY,
            base_rehearsal_id=base_report.rehearsal_id,
            base_rehearsal_report_path=str(base_path),
            base_rehearsal_report_sha256=rehearsal_report_sha256(base_path),
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            reason=(
                "all activation-consumption rehearsal scenarios passed"
                if passed
                else "one or more activation-consumption scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_activation_consumption_rehearsal(
    report_path: Path,
) -> ActivationConsumptionRehearsalReport:
    """Load an activation-consumption report and verify linked evidence."""
    report = ActivationConsumptionRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _dry_run_restart(
    root: Path, base_path: Path, evaluated_at: datetime
) -> ActivationConsumptionRehearsalScenarioResult:
    first = _run_dry("activation-dry-restart", root, base_path, evaluated_at)
    second = _run_dry("activation-dry-restart", root, base_path, evaluated_at)
    return _scenario_result(
        scenario=ActivationConsumptionRehearsalScenario.DRY_RUN_RESTART,
        results=(first, second),
        passed=(
            first == second
            and first.workflow is not None
            and first.workflow.record.status
            == SemanticTargetWorkflowStatus.DRY_RUN_OBSERVED
        ),
        root=root,
        reason="activated dry-run restart returned the same durable result",
    )


def _local_paper_restart(
    root: Path, base_path: Path, evaluated_at: datetime
) -> ActivationConsumptionRehearsalScenarioResult:
    first = _run_paper(
        "activation-paper-restart", root, base_path, evaluated_at
    )
    second = _run_paper(
        "activation-paper-restart", root, base_path, evaluated_at
    )
    scenario_root = root / "scenarios" / "activation-paper-restart"
    order_count = len(
        tuple((scenario_root / "workflow" / "semantic-paper" / "orders").glob(
            "*.json"
        ))
    )
    return _scenario_result(
        scenario=ActivationConsumptionRehearsalScenario.LOCAL_PAPER_RESTART,
        results=(first, second),
        passed=(
            first == second
            and first.workflow is not None
            and first.workflow.record.execution_status
            == ExecutionPlanStatus.SATISFIED
            and order_count == 1
        ),
        root=root,
        reason="activated local paper restart preserved one satisfied order",
    )


def _expired_authorization_block(
    root: Path, base_path: Path, evaluated_at: datetime
) -> ActivationConsumptionRehearsalScenarioResult:
    result = _run_dry(
        "activation-expired-block",
        root,
        base_path,
        evaluated_at,
        valid_until=evaluated_at,
    )
    return _scenario_result(
        scenario=(
            ActivationConsumptionRehearsalScenario.EXPIRED_AUTHORIZATION_BLOCK
        ),
        results=(result,),
        passed=(
            result.activation_evaluation.decision == ActivationDecision.BLOCKED
            and result.workflow is None
            and not (
                root / "scenarios" / "activation-expired-block" / "workflow"
            ).exists()
        ),
        root=root,
        reason="expired authorization blocked before target artifacts",
    )


def _scope_mismatch_block(
    root: Path, base_path: Path, evaluated_at: datetime
) -> ActivationConsumptionRehearsalScenarioResult:
    result = _run_paper(
        "activation-scope-block",
        root,
        base_path,
        evaluated_at,
        scopes=(SemanticTargetActivationScope.DRY_RUN,),
    )
    return _scenario_result(
        scenario=ActivationConsumptionRehearsalScenario.SCOPE_MISMATCH_BLOCK,
        results=(result,),
        passed=(
            result.activation_evaluation.decision == ActivationDecision.BLOCKED
            and result.workflow is None
            and not (
                root / "scenarios" / "activation-scope-block" / "workflow"
            ).exists()
        ),
        root=root,
        reason="scope mismatch blocked before local-paper artifacts",
    )


def _single_consumption_enforcement(
    root: Path, base_path: Path, evaluated_at: datetime
) -> ActivationConsumptionRehearsalScenarioResult:
    scenario_id = "activation-single-consumption"
    first = _run_dry(scenario_id, root, base_path, evaluated_at)
    conflict_root = root / "scenarios" / scenario_id / "conflicting-workflow"
    conflict_blocked = False
    try:
        _run_dry(
            scenario_id,
            root,
            base_path,
            evaluated_at,
            orchestration_id="conflicting-orchestration",
            workflow_root=conflict_root,
        )
    except ValueError as error:
        conflict_blocked = "consumption conflicts" in str(error)
    return _scenario_result(
        scenario=(
            ActivationConsumptionRehearsalScenario.SINGLE_CONSUMPTION_ENFORCEMENT
        ),
        results=(first,),
        passed=conflict_blocked and not conflict_root.exists(),
        root=root,
        reason="one activation evaluation could not authorize another run",
    )


def _run_dry(
    scenario_id: str,
    root: Path,
    base_path: Path,
    evaluated_at: datetime,
    *,
    valid_until: datetime | None = None,
    orchestration_id: str | None = None,
    workflow_root: Path | None = None,
) -> ActivatedSemanticTargetWorkflowResult:
    scenario_root = root / "scenarios" / scenario_id
    decision, evaluation = _target_inputs(scenario_id, evaluated_at)
    return run_activated_semantic_target_dry_run_workflow(
        activation_evaluation_id=f"evaluation-{scenario_id}",
        authorization=_authorization(
            scenario_id,
            base_path,
            evaluated_at,
            valid_until=valid_until,
        ),
        rehearsal_report_path=base_path,
        activation_root=scenario_root / "activation",
        orchestration_id=orchestration_id or scenario_id,
        contributor_set=_contributor_set(scenario_id),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=_risk_policy(),
        portfolio_target_id=f"portfolio-{scenario_id}",
        portfolio_target_revision=1,
        risk_target_id=f"risk-{scenario_id}",
        risk_target_revision=1,
        account=_account(evaluated_at),
        policy=_execution_policy(),
        reference_price=100,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.DRY_RUN,
            allowed=True,
        ),
        output_root=workflow_root or scenario_root / "workflow",
        evaluated_at=evaluated_at,
    )


def _run_paper(
    scenario_id: str,
    root: Path,
    base_path: Path,
    evaluated_at: datetime,
    *,
    scopes: tuple[SemanticTargetActivationScope, ...] = (
        SemanticTargetActivationScope.DRY_RUN,
        SemanticTargetActivationScope.SEMANTIC_PAPER,
    ),
) -> ActivatedSemanticTargetWorkflowResult:
    scenario_root = root / "scenarios" / scenario_id
    decision, evaluation = _target_inputs(scenario_id, evaluated_at)
    return run_activated_semantic_target_paper_workflow(
        activation_evaluation_id=f"evaluation-{scenario_id}",
        authorization=_authorization(
            scenario_id, base_path, evaluated_at, scopes=scopes
        ),
        rehearsal_report_path=base_path,
        activation_root=scenario_root / "activation",
        orchestration_id=scenario_id,
        contributor_set=_contributor_set(scenario_id),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=_risk_policy(),
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
        output_root=scenario_root / "workflow",
        initial_cash=1_000,
        evaluated_at=evaluated_at,
    )


def _authorization(
    scenario_id: str,
    base_path: Path,
    evaluated_at: datetime,
    *,
    scopes: tuple[SemanticTargetActivationScope, ...] = (
        SemanticTargetActivationScope.DRY_RUN,
        SemanticTargetActivationScope.SEMANTIC_PAPER,
    ),
    valid_until: datetime | None = None,
) -> SemanticTargetActivationAuthorization:
    base_report = load_and_verify_semantic_target_rehearsal(base_path)
    return SemanticTargetActivationAuthorization(
        authorization_id=f"authorization-{scenario_id}",
        revision=1,
        allowed_scopes=scopes,
        orchestration_policy_version=SEMANTIC_TARGET_ORCHESTRATION_POLICY,
        rehearsal_policy_version=SEMANTIC_TARGET_REHEARSAL_POLICY,
        rehearsal_id=base_report.rehearsal_id,
        rehearsal_report_sha256=rehearsal_report_sha256(base_path),
        issued_at=evaluated_at - timedelta(minutes=1),
        effective_at=evaluated_at - timedelta(seconds=1),
        valid_until=valid_until or evaluated_at + timedelta(hours=1),
        issued_by="local-activation-consumption-rehearsal",
        reason="controlled no-network activation-consumption rehearsal",
        evidence_refs=(str(base_path),),
    )


def _target_inputs(
    scenario_id: str,
    evaluated_at: datetime,
) -> tuple[StrategyTargetDecision, StrategyEvaluation]:
    decision_id = f"decision-{scenario_id}"
    decision = StrategyTargetDecision(
        decision_id=decision_id,
        revision=1,
        strategy_id="activation-rehearsal-strategy",
        strategy_version="1",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"synthetic-{scenario_id}",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled activation-consumption rehearsal target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"strategy-evaluation-{scenario_id}",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision_id,
        reason="controlled activation-consumption rehearsal evaluation",
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
                strategy_id="activation-rehearsal-strategy",
                strategy_version="1",
            ),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled activation-consumption ownership",
    )


def _risk_policy() -> ResearchRiskPolicy:
    return ResearchRiskPolicy(
        risk_policy_version="approve_or_reject_v1",
        max_absolute_target=Decimal("10"),
    )


def _execution_policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=(
            ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
        ),
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _account(evaluated_at: datetime) -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        id="activation-rehearsal-account",
        broker_name="local-activation-rehearsal",
        account_id="local-activation-rehearsal-account",
        broker_environment="dry_run",
        cash=1_000,
        buying_power=1_000,
        captured_at=evaluated_at,
    )


def _scenario_result(
    *,
    scenario: ActivationConsumptionRehearsalScenario,
    results: tuple[ActivatedSemanticTargetWorkflowResult, ...],
    passed: bool,
    root: Path,
    reason: str,
) -> ActivationConsumptionRehearsalScenarioResult:
    return ActivationConsumptionRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        activation_decisions=tuple(
            item.activation_evaluation.decision for item in results
        ),
        evaluation_ids=tuple(
            item.activation_evaluation.evaluation_id for item in results
        ),
        evaluation_paths=tuple(
            _evaluation_path(root, item) for item in results
        ),
        consumption_ids=tuple(
            item.activation_consumption.consumption_id for item in results
        ),
        consumption_paths=tuple(
            _consumption_path(root, item) for item in results
        ),
        workflow_orchestration_ids=tuple(
            item.workflow.record.orchestration_id
            for item in results
            if item.workflow is not None
        ),
        workflow_statuses=tuple(
            item.workflow.record.status.value
            for item in results
            if item.workflow is not None
        ),
        workflow_paths=tuple(
            _workflow_path(root, item)
            for item in results
            if item.workflow is not None
        ),
        reason=reason,
    )


def _evaluation_path(
    root: Path, result: ActivatedSemanticTargetWorkflowResult
) -> str:
    scenario_id = result.activation_consumption.orchestration_id
    return str(
        root
        / "scenarios"
        / scenario_id
        / "activation"
        / "evaluations"
        / f"{result.activation_evaluation.evaluation_id}.json"
    )


def _consumption_path(
    root: Path, result: ActivatedSemanticTargetWorkflowResult
) -> str:
    scenario_id = result.activation_consumption.orchestration_id
    return str(
        root
        / "scenarios"
        / scenario_id
        / "activation"
        / "consumptions"
        / f"{result.activation_evaluation.evaluation_id}.json"
    )


def _workflow_path(
    root: Path, result: ActivatedSemanticTargetWorkflowResult
) -> str:
    scenario_id = result.activation_consumption.orchestration_id
    return str(
        root
        / "scenarios"
        / scenario_id
        / "workflow"
        / "orchestrations"
        / f"{scenario_id}.json"
    )


def _verify_report_evidence(
    report: ActivationConsumptionRehearsalReport,
) -> None:
    base_path = Path(report.base_rehearsal_report_path)
    _require_evidence_file(base_path)
    base_report = load_and_verify_semantic_target_rehearsal(base_path)
    if (
        base_report.rehearsal_id != report.base_rehearsal_id
        or rehearsal_report_sha256(base_path)
        != report.base_rehearsal_report_sha256
    ):
        raise ValueError("base rehearsal evidence does not match report")
    for scenario in report.scenarios:
        for index, path_value in enumerate(scenario.evaluation_paths):
            _require_evidence_file(Path(path_value))
            evaluation = SemanticTargetActivationEvaluation.model_validate_json(
                Path(path_value).read_text()
            )
            if (
                evaluation.evaluation_id != scenario.evaluation_ids[index]
                or evaluation.decision
                != scenario.activation_decisions[index]
            ):
                raise ValueError("activation evaluation does not match report")
        for index, path_value in enumerate(scenario.consumption_paths):
            _require_evidence_file(Path(path_value))
            consumption = (
                SemanticTargetActivationConsumption.model_validate_json(
                    Path(path_value).read_text()
                )
            )
            if (
                consumption.consumption_id != scenario.consumption_ids[index]
                or consumption.activation_decision
                != scenario.activation_decisions[index]
            ):
                raise ValueError("activation consumption does not match report")
        for index, path_value in enumerate(scenario.workflow_paths):
            _require_evidence_file(Path(path_value))
            workflow = SemanticTargetWorkflowRecord.model_validate_json(
                Path(path_value).read_text()
            )
            if (
                workflow.orchestration_id
                != scenario.workflow_orchestration_ids[index]
                or workflow.status.value != scenario.workflow_statuses[index]
            ):
                raise ValueError("activation workflow does not match report")


def _require_evidence_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"activation rehearsal evidence is missing: {path}")


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
        raise ValueError(
            "activation rehearsal ID must be a safe path component"
        )
