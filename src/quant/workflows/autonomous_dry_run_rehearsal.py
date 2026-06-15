"""Run evidence-verified no-network autonomous dry-run rehearsals."""

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
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    AutonomousDryRunRecord,
    AutonomousDryRunRehearsalReport,
    AutonomousDryRunRehearsalScenario,
    AutonomousDryRunRehearsalScenarioResult,
    AutonomousDryRunRequest,
    AutonomousDryRunStatus,
)
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
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
from quant.models.workflow import SemanticTargetWorkflowRecord
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_record,
    run_authorized_autonomous_dry_run,
)

AUTONOMOUS_DRY_RUN_REHEARSAL_POLICY = "autonomous_dry_run_local_rehearsal_v1"


def run_autonomous_dry_run_local_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> AutonomousDryRunRehearsalReport:
    """Run deterministic autonomous dry-run scenarios and persist proof."""
    _require_safe_id(rehearsal_id)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"autonomous-dry-run-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = AutonomousDryRunRehearsalReport.model_validate_json(
                report_path.read_text()
            )
            if (
                report.evaluated_at != evaluated_at
                or report.rehearsal_policy_version
                != AUTONOMOUS_DRY_RUN_REHEARSAL_POLICY
            ):
                raise ValueError(
                    "autonomous rehearsal ID is already bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        scenarios = (
            _repeated_allowed_runs(output_root, evaluated_at),
            _restart_idempotency(output_root, evaluated_at),
            _expired_authorization_block(output_root, evaluated_at),
            _target_limit_block(output_root, evaluated_at),
            _halt_after_block(output_root, evaluated_at),
        )
        passed = all(item.passed for item in scenarios)
        report = AutonomousDryRunRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=AUTONOMOUS_DRY_RUN_REHEARSAL_POLICY,
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            reason=(
                "all bounded autonomous dry-run rehearsal scenarios passed"
                if passed
                else "one or more autonomous dry-run scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_autonomous_dry_run_rehearsal(
    report_path: Path,
) -> AutonomousDryRunRehearsalReport:
    """Load an autonomous dry-run rehearsal and verify linked evidence."""
    report = AutonomousDryRunRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _repeated_allowed_runs(
    root: Path, evaluated_at: datetime
) -> AutonomousDryRunRehearsalScenarioResult:
    scenario = AutonomousDryRunRehearsalScenario.REPEATED_ALLOWED_RUNS
    scenario_root = _scenario_root(root, scenario)
    authorization = _authorization(scenario, evaluated_at)
    first = _run(
        scenario_root, authorization, "allowed-1", evaluated_at
    )
    second = _run(
        scenario_root,
        authorization,
        "allowed-2",
        evaluated_at + timedelta(minutes=5),
    )
    return _scenario_result(
        scenario=scenario,
        root=scenario_root,
        authorization=authorization,
        records=(first, second),
        passed=all(
            item.status == AutonomousDryRunStatus.SUCCEEDED
            for item in (first, second)
        ),
        reason="two routine dry-runs ran under one bounded authorization",
    )


def _restart_idempotency(
    root: Path, evaluated_at: datetime
) -> AutonomousDryRunRehearsalScenarioResult:
    scenario = AutonomousDryRunRehearsalScenario.RESTART_IDEMPOTENCY
    scenario_root = _scenario_root(root, scenario)
    authorization = _authorization(scenario, evaluated_at)
    request = _request("restart", evaluated_at).model_copy(
        update={"authorization_id": authorization.authorization_id}
    )
    first = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=scenario_root,
        run_at=evaluated_at,
    )
    second = run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=scenario_root,
        run_at=evaluated_at,
    )
    return _scenario_result(
        scenario=scenario,
        root=scenario_root,
        authorization=authorization,
        records=(first, second),
        passed=first == second and _run_file_count(scenario_root) == 1,
        reason="restarting the same run returned one durable result",
    )


def _expired_authorization_block(
    root: Path, evaluated_at: datetime
) -> AutonomousDryRunRehearsalScenarioResult:
    scenario = AutonomousDryRunRehearsalScenario.EXPIRED_AUTHORIZATION_BLOCK
    scenario_root = _scenario_root(root, scenario)
    authorization = _authorization(
        scenario, evaluated_at, valid_until=evaluated_at
    )
    record = _run(scenario_root, authorization, "expired", evaluated_at)
    return _scenario_result(
        scenario=scenario,
        root=scenario_root,
        authorization=authorization,
        records=(record,),
        passed=(
            record.status == AutonomousDryRunStatus.BLOCKED
            and "authorization is expired" in record.reason
            and not (scenario_root / "workflows").exists()
        ),
        reason="expired authorization blocked before the dry-run workflow",
    )


def _target_limit_block(
    root: Path, evaluated_at: datetime
) -> AutonomousDryRunRehearsalScenarioResult:
    scenario = AutonomousDryRunRehearsalScenario.TARGET_LIMIT_BLOCK
    scenario_root = _scenario_root(root, scenario)
    authorization = _authorization(
        scenario, evaluated_at, max_absolute_target_shares=Decimal("2")
    )
    record = _run(
        scenario_root,
        authorization,
        "target-limit",
        evaluated_at,
        target=Decimal("3"),
    )
    return _scenario_result(
        scenario=scenario,
        root=scenario_root,
        authorization=authorization,
        records=(record,),
        passed=(
            record.status == AutonomousDryRunStatus.BLOCKED
            and "aggregate target exceeds authorization limit" in record.reason
            and not (scenario_root / "workflows").exists()
        ),
        reason="out-of-limit target blocked before the dry-run workflow",
    )


def _halt_after_block(
    root: Path, evaluated_at: datetime
) -> AutonomousDryRunRehearsalScenarioResult:
    scenario = AutonomousDryRunRehearsalScenario.HALT_AFTER_BLOCK
    scenario_root = _scenario_root(root, scenario)
    authorization = _authorization(scenario, evaluated_at)
    blocked = _run(
        scenario_root,
        authorization,
        "working-order-block",
        evaluated_at,
        open_order_ids=("working-order-1",),
    )
    later = _run(
        scenario_root,
        authorization,
        "halted-later-run",
        evaluated_at + timedelta(minutes=5),
    )
    return _scenario_result(
        scenario=scenario,
        root=scenario_root,
        authorization=authorization,
        records=(blocked, later),
        passed=(
            blocked.status == AutonomousDryRunStatus.BLOCKED
            and later.status == AutonomousDryRunStatus.BLOCKED
            and "prior autonomous run is blocked" in later.reason
            and later.orchestration_id is None
        ),
        reason="one blocked attempt halted later autonomous runs",
    )


def _run(
    root: Path,
    authorization: AutonomousDryRunAuthorization,
    run_id: str,
    run_at: datetime,
    *,
    target: Decimal = Decimal("2"),
    open_order_ids: tuple[str, ...] = (),
) -> AutonomousDryRunRecord:
    request = _request(
        run_id,
        run_at,
        target=target,
        open_order_ids=open_order_ids,
    ).model_copy(
        update={"authorization_id": authorization.authorization_id}
    )
    return run_authorized_autonomous_dry_run(
        authorization=authorization,
        request=request,
        output_root=root,
        run_at=run_at,
    )


def _authorization(
    scenario: AutonomousDryRunRehearsalScenario,
    evaluated_at: datetime,
    *,
    valid_until: datetime | None = None,
    max_absolute_target_shares: Decimal = Decimal("10"),
) -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id=f"rehearsal-{scenario.value}",
        revision=1,
        symbol="AAPL",
        contributor_set_id="rehearsal-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="local-autonomous-rehearsal",
        account_id="local-autonomous-rehearsal-account",
        max_absolute_target_shares=max_absolute_target_shares,
        maximum_runs=5,
        minimum_interval_seconds=60,
        issued_at=evaluated_at - timedelta(minutes=1),
        effective_at=evaluated_at - timedelta(seconds=1),
        valid_until=valid_until or evaluated_at + timedelta(hours=1),
        issued_by="local-autonomous-rehearsal",
        reason="controlled no-network autonomous dry-run rehearsal",
        evidence_refs=("rehearsal:no-network",),
    )


def _request(
    run_id: str,
    evaluated_at: datetime,
    *,
    target: Decimal = Decimal("2"),
    open_order_ids: tuple[str, ...] = (),
) -> AutonomousDryRunRequest:
    decision = StrategyTargetDecision(
        decision_id=f"{run_id}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target,
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{run_id}-input",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(minutes=30),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled autonomous rehearsal target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{run_id}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="controlled autonomous rehearsal evaluation",
    )
    return AutonomousDryRunRequest(
        run_id=run_id,
        authorization_id="rehearsal-placeholder",
        authorization_revision=1,
        orchestration_id=f"{run_id}-orchestration",
        contributor_set=_contributor_set(),
        strategy_decisions=(decision,),
        strategy_evaluations=(evaluation,),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id=f"{run_id}-portfolio",
        portfolio_target_revision=1,
        risk_target_id=f"{run_id}-risk",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id=f"{run_id}-account",
            broker_name="local-autonomous-rehearsal",
            account_id="local-autonomous-rehearsal-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            open_order_ids=open_order_ids,
            captured_at=evaluated_at,
        ),
        execution_policy=ExecutionLifecyclePolicy(
            execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
            reconciliation_policy_version=(
                ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY
            ),
            drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
        ),
        reference_price=100,
        evaluated_at=evaluated_at,
        evidence_refs=("rehearsal:no-network",),
    )


def _contributor_set() -> ContributorSet:
    return ContributorSet(
        contributor_set_id="rehearsal-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled autonomous rehearsal ownership",
    )


def _scenario_result(
    *,
    scenario: AutonomousDryRunRehearsalScenario,
    root: Path,
    authorization: AutonomousDryRunAuthorization,
    records: tuple[AutonomousDryRunRecord, ...],
    passed: bool,
    reason: str,
) -> AutonomousDryRunRehearsalScenarioResult:
    return AutonomousDryRunRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        authorization_path=str(
            root
            / "authorizations"
            / authorization.authorization_id
            / f"{authorization.revision}.json"
        ),
        run_ids=tuple(item.run_id for item in records),
        run_statuses=tuple(item.status for item in records),
        run_paths=tuple(
            str(root / "runs" / f"{item.run_id}.json") for item in records
        ),
        workflow_paths=tuple(
            str(
                root
                / "workflows"
                / "orchestrations"
                / f"{item.orchestration_id}.json"
            )
            for item in records
            if item.orchestration_id is not None
        ),
        reason=reason,
    )


def _scenario_root(
    root: Path, scenario: AutonomousDryRunRehearsalScenario
) -> Path:
    return root / "scenarios" / scenario.value


def _run_file_count(root: Path) -> int:
    return len(tuple((root / "runs").glob("*.json")))


def _verify_report_evidence(report: AutonomousDryRunRehearsalReport) -> None:
    for scenario in report.scenarios:
        authorization_path = Path(scenario.authorization_path)
        _require_evidence_file(authorization_path)
        authorization = AutonomousDryRunAuthorization.model_validate_json(
            authorization_path.read_text()
        )
        records: list[AutonomousDryRunRecord] = []
        for index, path_value in enumerate(scenario.run_paths):
            path = Path(path_value)
            _require_evidence_file(path)
            record = load_autonomous_dry_run_record(path)
            records.append(record)
            if (
                record.run_id != scenario.run_ids[index]
                or record.status != scenario.run_statuses[index]
                or record.authorization_id != authorization.authorization_id
                or record.authorization_revision != authorization.revision
            ):
                raise ValueError(
                    "autonomous rehearsal run evidence does not match report"
                )
        expected_workflow_records = tuple(
            item for item in records if item.orchestration_id is not None
        )
        if len(expected_workflow_records) != len(scenario.workflow_paths):
            raise ValueError(
                "autonomous rehearsal workflow evidence does not align"
            )
        for index, path_value in enumerate(scenario.workflow_paths):
            path = Path(path_value)
            _require_evidence_file(path)
            workflow = SemanticTargetWorkflowRecord.model_validate_json(
                path.read_text()
            )
            run_record = expected_workflow_records[index]
            if (
                workflow.orchestration_id != run_record.orchestration_id
                or workflow.status.value != run_record.workflow_status
                or (
                    workflow.dry_run_status.value
                    if workflow.dry_run_status is not None
                    else None
                )
                != run_record.dry_run_status
            ):
                raise ValueError(
                    "autonomous rehearsal workflow does not match run record"
                )


def _require_evidence_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"autonomous rehearsal evidence is missing: {path}")


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
            "autonomous rehearsal ID must be a safe path component"
        )
