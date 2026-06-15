"""Run evidence-verified no-network supervised dry-run service rehearsals."""

import json
import os
from contextlib import suppress
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
    AutonomousDryRunRequest,
    SupervisedDryRunCycleEvent,
    SupervisedDryRunHealthCheck,
    SupervisedDryRunHealthStatus,
    SupervisedDryRunRehearsalReport,
    SupervisedDryRunRehearsalScenario,
    SupervisedDryRunRehearsalScenarioResult,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceRecord,
    SupervisedDryRunServiceStatus,
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
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import load_autonomous_dry_run_record
from quant.workflows.supervised_autonomous_dry_run import (
    load_supervised_dry_run_service_record,
    run_supervised_autonomous_dry_run_service,
)

SUPERVISED_DRY_RUN_REHEARSAL_POLICY = (
    "supervised_autonomous_dry_run_local_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_supervised_autonomous_dry_run_local_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> SupervisedDryRunRehearsalReport:
    """Run deterministic supervisor scenarios and persist verified proof."""
    _require_safe_id(rehearsal_id)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"supervised-dry-run-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = SupervisedDryRunRehearsalReport.model_validate_json(
                report_path.read_text()
            )
            if (
                report.evaluated_at != evaluated_at
                or report.rehearsal_policy_version
                != SUPERVISED_DRY_RUN_REHEARSAL_POLICY
            ):
                raise ValueError(
                    "supervised rehearsal ID is already bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        evidence_root = output_root / "scenarios"
        scenarios = (
            _healthy_continuation(evidence_root, evaluated_at),
            _health_stop(
                evidence_root,
                evaluated_at,
                SupervisedDryRunRehearsalScenario.DEGRADED_HEALTH_STOP,
                SupervisedDryRunHealthStatus.DEGRADED,
            ),
            _health_stop(
                evidence_root,
                evaluated_at,
                SupervisedDryRunRehearsalScenario.FAILED_HEALTH_STOP,
                SupervisedDryRunHealthStatus.FAILED,
            ),
            _shutdown_stop(evidence_root, evaluated_at),
            _blocked_run_stop(evidence_root, evaluated_at),
            _provider_error_stop(evidence_root, evaluated_at),
            _runtime_bound_stop(evidence_root, evaluated_at),
            _restart_continuation(evidence_root, evaluated_at),
        )
        prohibited = _prohibited_artifact_paths(evidence_root)
        passed = all(item.passed for item in scenarios) and not prohibited
        report = SupervisedDryRunRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=SUPERVISED_DRY_RUN_REHEARSAL_POLICY,
            evidence_root=str(evidence_root),
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            prohibited_artifact_paths=prohibited,
            reason=(
                "all supervised dry-run service rehearsal scenarios passed"
                if passed
                else "one or more supervised service scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_supervised_autonomous_dry_run_rehearsal(
    report_path: Path,
) -> SupervisedDryRunRehearsalReport:
    """Load a supervised-service rehearsal and verify linked evidence."""
    report = SupervisedDryRunRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _healthy_continuation(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.HEALTHY_CONTINUATION
    record = _run_service(
        root,
        scenario,
        evaluated_at,
        maximum_cycles=2,
        interval_seconds=60,
        clock=_Clock(
            evaluated_at,
            evaluated_at,
            evaluated_at + timedelta(minutes=1),
        ),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.COMPLETED
            and record.completed_cycles == 2
        ),
        reason="two healthy cycles completed inside the service bounds",
    )


def _health_stop(
    root: Path,
    evaluated_at: datetime,
    scenario: SupervisedDryRunRehearsalScenario,
    status: SupervisedDryRunHealthStatus,
) -> SupervisedDryRunRehearsalScenarioResult:
    record = _run_service(
        root,
        scenario,
        evaluated_at,
        health_provider=lambda cycle, now: _health(
            scenario, cycle, now, status
        ),
        clock=_Clock(evaluated_at, evaluated_at),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.STOPPED
            and record.completed_cycles == 0
            and not record.run_ids
        ),
        reason=f"{status.value} health stopped before request generation",
    )


def _shutdown_stop(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.EXPLICIT_SHUTDOWN_STOP
    record = _run_service(
        root,
        scenario,
        evaluated_at,
        shutdown_requested=lambda: True,
        clock=_Clock(evaluated_at, evaluated_at),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.STOPPED
            and "shutdown" in record.reason
            and not record.run_ids
        ),
        reason="explicit shutdown stopped before health and request generation",
    )


def _blocked_run_stop(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.BLOCKED_RUN_STOP
    record = _run_service(
        root,
        scenario,
        evaluated_at,
        request_provider=lambda cycle, now: _request(
            scenario,
            cycle,
            now,
            open_order_ids=("working-order-1",),
        ),
        clock=_Clock(evaluated_at, evaluated_at),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.STOPPED
            and record.completed_cycles == 0
            and len(record.run_ids) == 1
        ),
        reason="working-order block stopped the service after one attempt",
    )


def _provider_error_stop(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.PROVIDER_ERROR_STOP

    def fail(_: int, __: datetime) -> AutonomousDryRunRequest:
        raise RuntimeError("synthetic request provider failure")

    record = _run_service(
        root,
        scenario,
        evaluated_at,
        request_provider=fail,
        clock=_Clock(evaluated_at, evaluated_at),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.STOPPED
            and "synthetic request provider failure" in record.reason
            and not record.run_ids
        ),
        reason="request-provider failure became a durable stop",
    )


def _runtime_bound_stop(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.RUNTIME_BOUND_STOP
    record = _run_service(
        root,
        scenario,
        evaluated_at,
        maximum_runtime_seconds=30,
        clock=_Clock(evaluated_at, evaluated_at + timedelta(seconds=30)),
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.STOPPED
            and "maximum runtime" in record.reason
            and not record.run_ids
        ),
        reason="maximum runtime stopped before health and request generation",
    )


def _restart_continuation(
    root: Path, evaluated_at: datetime
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario = SupervisedDryRunRehearsalScenario.RESTART_CONTINUATION
    scenario_root = _scenario_root(root, scenario)
    policy = _policy(
        scenario, evaluated_at, maximum_cycles=2, interval_seconds=60
    )
    authorization = _authorization(scenario, evaluated_at)

    def interrupt_after_event(_: float) -> None:
        raise KeyboardInterrupt

    with suppress(KeyboardInterrupt):
        run_supervised_autonomous_dry_run_service(
            policy=policy,
            authorization=authorization,
            request_provider=lambda cycle, now: _request(scenario, cycle, now),
            health_provider=lambda cycle, now: _health(scenario, cycle, now),
            shutdown_requested=lambda: False,
            output_root=scenario_root,
            clock=_Clock(evaluated_at, evaluated_at),
            sleeper=interrupt_after_event,
        )
    record = run_supervised_autonomous_dry_run_service(
        policy=policy,
        authorization=authorization,
        request_provider=lambda cycle, now: _request(scenario, cycle, now),
        health_provider=lambda cycle, now: _health(scenario, cycle, now),
        shutdown_requested=lambda: False,
        output_root=scenario_root,
        clock=_Clock(evaluated_at + timedelta(minutes=1)),
        sleeper=lambda _: None,
    )
    return _scenario_result(
        scenario,
        root,
        record,
        passed=(
            record.status == SupervisedDryRunServiceStatus.COMPLETED
            and record.completed_cycles == 2
            and len(record.run_ids) == 2
        ),
        reason="restart continued after the last durable successful cycle",
    )


def _run_service(
    root: Path,
    scenario: SupervisedDryRunRehearsalScenario,
    evaluated_at: datetime,
    *,
    maximum_cycles: int = 3,
    interval_seconds: float = 0,
    maximum_runtime_seconds: float = 3600,
    request_provider=None,
    health_provider=None,
    shutdown_requested=None,
    clock,
) -> SupervisedDryRunServiceRecord:
    return run_supervised_autonomous_dry_run_service(
        policy=_policy(
            scenario,
            evaluated_at,
            maximum_cycles=maximum_cycles,
            interval_seconds=interval_seconds,
            maximum_runtime_seconds=maximum_runtime_seconds,
        ),
        authorization=_authorization(scenario, evaluated_at),
        request_provider=request_provider
        or (lambda cycle, now: _request(scenario, cycle, now)),
        health_provider=health_provider
        or (lambda cycle, now: _health(scenario, cycle, now)),
        shutdown_requested=shutdown_requested or (lambda: False),
        output_root=_scenario_root(root, scenario),
        clock=clock,
        sleeper=lambda _: None,
    )


def _policy(
    scenario: SupervisedDryRunRehearsalScenario,
    evaluated_at: datetime,
    *,
    maximum_cycles: int = 3,
    interval_seconds: float = 0,
    maximum_runtime_seconds: float = 3600,
) -> SupervisedDryRunServicePolicy:
    return SupervisedDryRunServicePolicy(
        service_id=scenario.value,
        policy_version="bounded_supervised_dry_run_v1",
        authorization_id=f"authorization-{scenario.value}",
        authorization_revision=1,
        maximum_cycles=maximum_cycles,
        interval_seconds=interval_seconds,
        maximum_runtime_seconds=maximum_runtime_seconds,
        created_at=evaluated_at,
        evidence_refs=("rehearsal:no-network",),
    )


def _authorization(
    scenario: SupervisedDryRunRehearsalScenario,
    evaluated_at: datetime,
) -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id=f"authorization-{scenario.value}",
        revision=1,
        symbol="AAPL",
        contributor_set_id="supervised-rehearsal-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="local-supervised-rehearsal",
        account_id="local-supervised-rehearsal-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=5,
        minimum_interval_seconds=0,
        issued_at=evaluated_at - timedelta(minutes=1),
        effective_at=evaluated_at - timedelta(seconds=1),
        valid_until=evaluated_at + timedelta(hours=2),
        issued_by="local-supervised-rehearsal",
        reason="controlled no-network supervised dry-run rehearsal",
        evidence_refs=("rehearsal:no-network",),
    )


def _health(
    scenario: SupervisedDryRunRehearsalScenario,
    cycle: int,
    checked_at: datetime,
    status: SupervisedDryRunHealthStatus = SupervisedDryRunHealthStatus.HEALTHY,
) -> SupervisedDryRunHealthCheck:
    return SupervisedDryRunHealthCheck(
        check_id=f"{scenario.value}-health-{cycle}",
        service_id=scenario.value,
        cycle_index=cycle,
        status=status,
        checked_at=checked_at,
        reasons=(
            ()
            if status == SupervisedDryRunHealthStatus.HEALTHY
            else (f"synthetic {status.value} health",)
        ),
        evidence_refs=("rehearsal:no-network",),
    )


def _request(
    scenario: SupervisedDryRunRehearsalScenario,
    cycle: int,
    evaluated_at: datetime,
    *,
    open_order_ids: tuple[str, ...] = (),
) -> AutonomousDryRunRequest:
    run_id = f"{scenario.value}-run-{cycle}"
    decision = StrategyTargetDecision(
        decision_id=f"{run_id}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{run_id}-input",
        generated_at=evaluated_at,
        effective_at=evaluated_at,
        valid_until=evaluated_at + timedelta(hours=1),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled supervised rehearsal target",
    )
    evaluation = StrategyEvaluation(
        evaluation_id=f"{run_id}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=evaluated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="controlled supervised rehearsal evaluation",
    )
    return AutonomousDryRunRequest(
        run_id=run_id,
        authorization_id=f"authorization-{scenario.value}",
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
            broker_name="local-supervised-rehearsal",
            account_id="local-supervised-rehearsal-account",
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
        contributor_set_id="supervised-rehearsal-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=3600,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled supervised rehearsal ownership",
    )


def _scenario_result(
    scenario: SupervisedDryRunRehearsalScenario,
    root: Path,
    record: SupervisedDryRunServiceRecord,
    *,
    passed: bool,
    reason: str,
) -> SupervisedDryRunRehearsalScenarioResult:
    scenario_root = _scenario_root(root, scenario)
    service_root = scenario_root / "services" / scenario.value
    events = tuple(
        SupervisedDryRunCycleEvent.model_validate_json(path.read_text())
        for path in map(Path, record.cycle_event_paths)
    )
    health_paths = tuple(
        str(service_root / "health-checks" / f"{item.health_check_id}.json")
        for item in events
        if item.health_check_id is not None
    )
    run_paths = tuple(
        str(scenario_root / "autonomous" / "runs" / f"{run_id}.json")
        for run_id in record.run_ids
    )
    return SupervisedDryRunRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        service_id=record.service_id,
        service_status=record.status,
        cycle_outcomes=tuple(item.outcome for item in events),
        service_record_path=str(service_root / "record.json"),
        cycle_event_paths=record.cycle_event_paths,
        health_check_paths=health_paths,
        run_record_paths=run_paths,
        reason=reason,
    )


def _verify_report_evidence(report: SupervisedDryRunRehearsalReport) -> None:
    evidence_root = Path(report.evidence_root)
    if not evidence_root.is_dir():
        raise ValueError(
            f"supervised rehearsal evidence is missing: {evidence_root}"
        )
    prohibited = _prohibited_artifact_paths(evidence_root)
    if prohibited != report.prohibited_artifact_paths:
        raise ValueError("supervised rehearsal prohibited evidence changed")
    for scenario in report.scenarios:
        record_path = Path(scenario.service_record_path)
        _require_evidence_file(record_path)
        record = load_supervised_dry_run_service_record(record_path)
        if (
            record.service_id != scenario.service_id
            or record.status != scenario.service_status
            or record.cycle_event_paths != scenario.cycle_event_paths
        ):
            raise ValueError("supervised service record does not match report")
        events = []
        for index, path_value in enumerate(scenario.cycle_event_paths):
            path = Path(path_value)
            _require_evidence_file(path)
            event = SupervisedDryRunCycleEvent.model_validate_json(
                path.read_text()
            )
            events.append(event)
            if (
                event.service_id != scenario.service_id
                or event.outcome != scenario.cycle_outcomes[index]
                or event.sequence != index + 1
            ):
                raise ValueError("supervised cycle event does not match report")
        expected_health_ids = tuple(
            item.health_check_id
            for item in events
            if item.health_check_id is not None
        )
        if len(expected_health_ids) != len(scenario.health_check_paths):
            raise ValueError("supervised health evidence does not align")
        for index, path_value in enumerate(scenario.health_check_paths):
            path = Path(path_value)
            _require_evidence_file(path)
            health = SupervisedDryRunHealthCheck.model_validate_json(
                path.read_text()
            )
            if (
                health.check_id != expected_health_ids[index]
                or health.service_id != scenario.service_id
            ):
                raise ValueError(
                    "supervised health check does not match report"
                )
        expected_run_ids = tuple(
            item.run_id for item in events if item.run_id is not None
        )
        if expected_run_ids != record.run_ids or len(expected_run_ids) != len(
            scenario.run_record_paths
        ):
            raise ValueError("supervised run evidence does not align")
        for index, path_value in enumerate(scenario.run_record_paths):
            path = Path(path_value)
            _require_evidence_file(path)
            run = load_autonomous_dry_run_record(path)
            matching_event = next(
                item
                for item in events
                if item.run_id == expected_run_ids[index]
            )
            if (
                run.run_id != expected_run_ids[index]
                or run.status != matching_event.run_status
            ):
                raise ValueError("supervised run record does not match report")


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    if not root.exists():
        return ()
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _scenario_root(
    root: Path, scenario: SupervisedDryRunRehearsalScenario
) -> Path:
    return root / scenario.value


def _require_evidence_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(f"supervised rehearsal evidence is missing: {path}")


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
            "supervised rehearsal ID must be a safe path component"
        )


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)
