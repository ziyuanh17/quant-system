"""Run evidence-verified no-network provider-assembly rehearsals."""

import json
import os
from datetime import datetime, timedelta
from decimal import Decimal
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.execution import (
    ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
    DETECT_ONLY_DRIFT_POLICY,
    SINGLE_MARKET_ORDER_POLICY,
)
from quant.models.autonomous import (
    AutonomousDryRunAuthorization,
    SupervisedDryRunServicePolicy,
    SupervisedDryRunServiceStatus,
    SupervisedProviderAssemblyManifest,
    SupervisedProviderAssemblyRecord,
    SupervisedProviderAssemblyRehearsalOutcome,
    SupervisedProviderAssemblyRehearsalReport,
    SupervisedProviderAssemblyRehearsalScenario,
    SupervisedProviderAssemblyRehearsalScenarioResult,
    SupervisedProviderPolicy,
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
from quant.research import (
    write_contributor_set,
    write_strategy_evaluation,
    write_strategy_target_decision,
)
from quant.workflows.autonomous_dry_run import (
    write_autonomous_dry_run_authorization,
)
from quant.workflows.supervised_autonomous_dry_run import (
    load_supervised_dry_run_service_record,
    run_supervised_autonomous_dry_run_service,
)
from quant.workflows.supervised_provider_assembly import (
    LOCAL_HEALTH_SOURCE_ID,
    LOCAL_PROVIDER_ASSEMBLY_VERSION,
    LOCAL_REQUEST_SOURCE_ID,
    assemble_local_supervised_provider_inputs,
    load_supervised_provider_assembly_record,
)
from quant.workflows.supervised_provider_inputs import (
    evaluate_supervised_health_snapshot,
    load_supervised_health_snapshot,
    load_supervised_request_envelope,
    resolve_supervised_request_envelope,
    write_supervised_provider_policy,
)

SUPERVISED_PROVIDER_ASSEMBLY_REHEARSAL_POLICY = (
    "supervised_provider_assembly_local_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_supervised_provider_assembly_local_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> SupervisedProviderAssemblyRehearsalReport:
    """Run deterministic provider-assembly scenarios and persist proof."""
    _require_safe_id(rehearsal_id)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"provider-assembly-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = (
                SupervisedProviderAssemblyRehearsalReport.model_validate_json(
                    report_path.read_text()
                )
            )
            if (
                report.evaluated_at != evaluated_at
                or report.rehearsal_policy_version
                != SUPERVISED_PROVIDER_ASSEMBLY_REHEARSAL_POLICY
            ):
                raise ValueError(
                    "provider-assembly rehearsal ID is bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        evidence_root = output_root / "scenarios"
        scenarios = (
            _successful_assembly(evidence_root, evaluated_at),
            _restart_reuse(evidence_root, evaluated_at),
            _changed_input_rejected(evidence_root, evaluated_at),
            _changed_output_detected(evidence_root, evaluated_at),
            _stale_target_rejected(evidence_root, evaluated_at),
            _stale_account_rejected(evidence_root, evaluated_at),
            _provider_to_supervisor(evidence_root, evaluated_at),
        )
        prohibited = _prohibited_artifact_paths(evidence_root)
        passed = all(item.passed for item in scenarios) and not prohibited
        report = SupervisedProviderAssemblyRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=(
                SUPERVISED_PROVIDER_ASSEMBLY_REHEARSAL_POLICY
            ),
            evidence_root=str(evidence_root),
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            prohibited_artifact_paths=prohibited,
            reason=(
                "all local provider-assembly rehearsal scenarios passed"
                if passed
                else "one or more provider-assembly scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_supervised_provider_assembly_rehearsal(
    report_path: Path,
) -> SupervisedProviderAssemblyRehearsalReport:
    """Load a provider-assembly rehearsal and verify linked evidence."""
    report = SupervisedProviderAssemblyRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _successful_assembly(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = SupervisedProviderAssemblyRehearsalScenario.SUCCESSFUL_ASSEMBLY
    scenario_root, manifest, _ = _inputs(root, scenario, now)
    record = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=scenario_root / "output"
    )
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.ASSEMBLED,
        assembly_records=(record,),
        passed=True,
        reason="reviewed local artifacts assembled into provider inputs",
    )


def _restart_reuse(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = SupervisedProviderAssemblyRehearsalScenario.RESTART_REUSE
    scenario_root, manifest, _ = _inputs(root, scenario, now)
    first = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=scenario_root / "output"
    )
    second = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=scenario_root / "output"
    )
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.ASSEMBLED,
        assembly_records=(first,),
        passed=first == second,
        reason="restart reused the exact verified provider assembly",
    )


def _changed_input_rejected(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = (
        SupervisedProviderAssemblyRehearsalScenario.CHANGED_INPUT_REJECTED
    )
    scenario_root, manifest, _ = _inputs(root, scenario, now)
    path = Path(manifest.strategy_decision_paths[0])
    path.write_text(path.read_text().replace('"2"', '"3"', 1))
    error = _capture_rejection(manifest, scenario_root / "output")
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.REJECTED,
        passed="input hash does not match" in error,
        reason=error,
    )


def _changed_output_detected(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = (
        SupervisedProviderAssemblyRehearsalScenario.CHANGED_OUTPUT_DETECTED
    )
    scenario_root, manifest, _ = _inputs(root, scenario, now)
    record = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=scenario_root / "output"
    )
    path = Path(record.health_snapshot_path)
    path.write_text(path.read_text().replace('"healthy"', '"failed"', 1))
    error = _capture_rejection(manifest, scenario_root / "output")
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.REJECTED,
        assembly_records=(record,),
        passed="output hash does not match" in error,
        reason=error,
    )


def _stale_target_rejected(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = SupervisedProviderAssemblyRehearsalScenario.STALE_TARGET_REJECTED
    scenario_root, manifest, _ = _inputs(
        root, scenario, now, decision_generated_at=now - timedelta(minutes=6)
    )
    error = _capture_rejection(manifest, scenario_root / "output")
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.REJECTED,
        passed="do not aggregate actively" in error,
        reason=error,
    )


def _stale_account_rejected(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = (
        SupervisedProviderAssemblyRehearsalScenario.STALE_ACCOUNT_REJECTED
    )
    scenario_root, manifest, _ = _inputs(
        root, scenario, now, account_captured_at=now - timedelta(minutes=6)
    )
    error = _capture_rejection(manifest, scenario_root / "output")
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.REJECTED,
        passed="account snapshot is stale" in error,
        reason=error,
    )


def _provider_to_supervisor(
    root: Path, now: datetime
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    scenario = (
        SupervisedProviderAssemblyRehearsalScenario.PROVIDER_TO_SUPERVISOR
    )
    scenario_root, manifest, authorization = _inputs(root, scenario, now)
    assembly = assemble_local_supervised_provider_inputs(
        manifest=manifest, output_root=scenario_root / "output"
    )
    health = load_supervised_health_snapshot(
        Path(assembly.health_snapshot_path)
    )
    envelope = load_supervised_request_envelope(
        Path(assembly.request_envelope_path)
    )
    policy = _policy(scenario, authorization)
    service = run_supervised_autonomous_dry_run_service(
        policy=SupervisedDryRunServicePolicy(
            service_id=scenario.value,
            policy_version="bounded_supervised_dry_run_v1",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            maximum_cycles=1,
            interval_seconds=0,
            maximum_runtime_seconds=60,
            created_at=now,
        ),
        authorization=authorization,
        health_provider=lambda cycle, checked_at: (
            evaluate_supervised_health_snapshot(
                policy=policy,
                snapshot=health,
                cycle_index=cycle,
                checked_at=checked_at,
            )
        ),
        request_provider=lambda cycle, requested_at: (
            resolve_supervised_request_envelope(
                policy=policy,
                authorization=authorization,
                envelope=envelope,
                cycle_index=cycle,
                requested_at=requested_at,
            )
        ),
        shutdown_requested=lambda: False,
        output_root=scenario_root / "service",
        clock=_Clock(now, now),
        sleeper=lambda _: None,
    )
    service_path = (
        scenario_root / "service" / "services" / scenario.value / "record.json"
    )
    return _result(
        scenario,
        scenario_root,
        outcome=SupervisedProviderAssemblyRehearsalOutcome.SUPERVISOR_COMPLETED,
        assembly_records=(assembly,),
        service_paths=(str(service_path),),
        passed=service.status == SupervisedDryRunServiceStatus.COMPLETED,
        reason=(
            "assembled provider inputs completed one supervised dry-run cycle"
        ),
    )


def _inputs(
    root: Path,
    scenario: SupervisedProviderAssemblyRehearsalScenario,
    now: datetime,
    *,
    decision_generated_at: datetime | None = None,
    account_captured_at: datetime | None = None,
) -> tuple[
    Path, SupervisedProviderAssemblyManifest, AutonomousDryRunAuthorization
]:
    scenario_root = root / scenario.value
    inputs = scenario_root / "inputs"
    authorization = _authorization(scenario, now)
    policy_path = write_supervised_provider_policy(
        _policy(scenario, authorization), inputs
    )
    authorization_path = write_autonomous_dry_run_authorization(
        authorization, inputs / "authorizations"
    )
    contributor_path = write_contributor_set(
        _contributor_set(scenario), inputs / "contributor-sets"
    )
    decision = _decision(scenario, now, decision_generated_at)
    decision_path = write_strategy_target_decision(
        decision, inputs / "strategy-targets"
    )
    evaluation_path = write_strategy_evaluation(
        _evaluation(scenario, decision, now), inputs / "strategy-evaluations"
    )
    manifest = SupervisedProviderAssemblyManifest(
        assembly_id=f"{scenario.value}-assembly",
        service_id=scenario.value,
        cycle_index=1,
        provider_policy_path=str(policy_path),
        provider_policy_sha256=_file_sha256(policy_path),
        authorization_path=str(authorization_path),
        authorization_sha256=_file_sha256(authorization_path),
        contributor_set_path=str(contributor_path),
        contributor_set_sha256=_file_sha256(contributor_path),
        strategy_decision_paths=(str(decision_path),),
        strategy_decision_sha256s=(_file_sha256(decision_path),),
        strategy_evaluation_paths=(str(evaluation_path),),
        strategy_evaluation_sha256s=(_file_sha256(evaluation_path),),
        risk_policy=ResearchRiskPolicy(
            risk_policy_version="approve_or_reject_v1",
            max_absolute_target=Decimal("10"),
        ),
        portfolio_target_id=f"{scenario.value}-portfolio",
        portfolio_target_revision=1,
        risk_target_id=f"{scenario.value}-risk",
        risk_target_revision=1,
        account=LiveAccountSnapshot(
            id=f"{scenario.value}-account-snapshot",
            broker_name="local-provider-rehearsal",
            account_id="local-provider-rehearsal-account",
            broker_environment="dry_run",
            cash=1_000,
            buying_power=1_000,
            captured_at=account_captured_at or now,
        ),
        execution_policy=_execution_policy(),
        reference_price=100,
        generated_at=now,
        valid_until=now + timedelta(minutes=5),
        evidence_refs=("rehearsal:no-network",),
    )
    return scenario_root, manifest, authorization


def _policy(
    scenario: SupervisedProviderAssemblyRehearsalScenario,
    authorization: AutonomousDryRunAuthorization,
) -> SupervisedProviderPolicy:
    return SupervisedProviderPolicy(
        provider_policy_version="supervised_provider_inputs_v1",
        service_id=scenario.value,
        authorization_id=authorization.authorization_id,
        authorization_revision=authorization.revision,
        health_source_id=LOCAL_HEALTH_SOURCE_ID,
        health_source_version=LOCAL_PROVIDER_ASSEMBLY_VERSION,
        request_source_id=LOCAL_REQUEST_SOURCE_ID,
        request_source_version=LOCAL_PROVIDER_ASSEMBLY_VERSION,
        required_health_components=(
            "semantic-targets",
            "dry-run-account",
            "execution-inputs",
        ),
        maximum_health_age_seconds=300,
        maximum_request_age_seconds=300,
        evidence_refs=("rehearsal:no-network",),
    )


def _authorization(
    scenario: SupervisedProviderAssemblyRehearsalScenario, now: datetime
) -> AutonomousDryRunAuthorization:
    return AutonomousDryRunAuthorization(
        authorization_id=f"{scenario.value}-authorization",
        revision=1,
        symbol="AAPL",
        contributor_set_id=f"{scenario.value}-contributors",
        contributor_set_revision=1,
        allowed_strategies=(("momentum", "2"),),
        broker_name="local-provider-rehearsal",
        account_id="local-provider-rehearsal-account",
        max_absolute_target_shares=Decimal("10"),
        maximum_runs=2,
        minimum_interval_seconds=0,
        issued_at=now - timedelta(minutes=1),
        effective_at=now - timedelta(seconds=1),
        valid_until=now + timedelta(hours=1),
        issued_by="local-provider-assembly-rehearsal",
        reason="controlled no-network provider-assembly rehearsal",
        evidence_refs=("rehearsal:no-network",),
    )


def _contributor_set(
    scenario: SupervisedProviderAssemblyRehearsalScenario,
) -> ContributorSet:
    return ContributorSet(
        contributor_set_id=f"{scenario.value}-contributors",
        revision=1,
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        expected_contributors=(
            ContributorSpec(strategy_id="momentum", strategy_version="2"),
        ),
        max_age_seconds=300,
        portfolio_policy_version="sum_active_targets_v1",
        reason="controlled provider-assembly rehearsal ownership",
    )


def _decision(
    scenario: SupervisedProviderAssemblyRehearsalScenario,
    now: datetime,
    generated_at: datetime | None,
) -> StrategyTargetDecision:
    decision_time = generated_at or now
    return StrategyTargetDecision(
        decision_id=f"{scenario.value}-decision",
        revision=1,
        strategy_id="momentum",
        strategy_version="2",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=Decimal("2"),
        sizing_policy_version="fixed_shares_v1",
        input_data_id=f"{scenario.value}-input",
        generated_at=decision_time,
        effective_at=decision_time,
        valid_until=now + timedelta(minutes=5),
        declared_status=TargetDeclaredStatus.ACTIVE,
        reason="controlled provider-assembly rehearsal target",
    )


def _evaluation(
    scenario: SupervisedProviderAssemblyRehearsalScenario,
    decision: StrategyTargetDecision,
    now: datetime,
) -> StrategyEvaluation:
    return StrategyEvaluation(
        evaluation_id=f"{scenario.value}-evaluation",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=now,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="controlled provider-assembly rehearsal evaluation",
    )


def _execution_policy() -> ExecutionLifecyclePolicy:
    return ExecutionLifecyclePolicy(
        execution_policy_version=SINGLE_MARKET_ORDER_POLICY,
        reconciliation_policy_version=ACCOUNT_WIDE_EXACT_RECONCILIATION_POLICY,
        drift_policy_version=DETECT_ONLY_DRIFT_POLICY,
    )


def _capture_rejection(
    manifest: SupervisedProviderAssemblyManifest, output_root: Path
) -> str:
    try:
        assemble_local_supervised_provider_inputs(
            manifest=manifest, output_root=output_root
        )
    except ValueError as error:
        return str(error)
    return "provider assembly unexpectedly succeeded"


def _result(
    scenario: SupervisedProviderAssemblyRehearsalScenario,
    scenario_root: Path,
    *,
    outcome: SupervisedProviderAssemblyRehearsalOutcome,
    passed: bool,
    reason: str,
    assembly_records: tuple[SupervisedProviderAssemblyRecord, ...] = (),
    service_paths: tuple[str, ...] = (),
) -> SupervisedProviderAssemblyRehearsalScenarioResult:
    evidence_paths = tuple(
        str(path)
        for path in sorted(scenario_root.rglob("*.json"))
        if path.is_file()
    )
    return SupervisedProviderAssemblyRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        outcome=outcome,
        assembly_record_paths=tuple(
            str(
                scenario_root
                / "output"
                / "assemblies"
                / item.assembly_id
                / "record.json"
            )
            for item in assembly_records
        ),
        service_record_paths=service_paths,
        evidence_paths=evidence_paths,
        reason=reason,
    )


def _verify_report_evidence(
    report: SupervisedProviderAssemblyRehearsalReport,
) -> None:
    root = Path(report.evidence_root)
    if not root.is_dir():
        raise ValueError(
            f"provider-assembly rehearsal evidence is missing: {root}"
        )
    if _prohibited_artifact_paths(root) != report.prohibited_artifact_paths:
        raise ValueError("provider-assembly prohibited evidence changed")
    for scenario in report.scenarios:
        for path_value in scenario.evidence_paths:
            _require_evidence_file(Path(path_value))
        for path_value in scenario.assembly_record_paths:
            path = Path(path_value)
            _require_evidence_file(path)
            record = load_supervised_provider_assembly_record(path)
            if scenario.scenario != (
                SupervisedProviderAssemblyRehearsalScenario.CHANGED_OUTPUT_DETECTED
            ):
                health_path = Path(record.health_snapshot_path)
                envelope_path = Path(record.request_envelope_path)
                _require_evidence_file(health_path)
                _require_evidence_file(envelope_path)
                if (
                    _file_sha256(health_path) != record.health_snapshot_sha256
                    or _file_sha256(envelope_path)
                    != record.request_envelope_sha256
                ):
                    raise ValueError(
                        "provider-assembly output does not match record"
                    )
        for path_value in scenario.service_record_paths:
            path = Path(path_value)
            _require_evidence_file(path)
            service = load_supervised_dry_run_service_record(path)
            if service.status != SupervisedDryRunServiceStatus.COMPLETED:
                raise ValueError(
                    "provider-assembly service evidence is not complete"
                )


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _require_evidence_file(path: Path) -> None:
    if not path.is_file():
        raise ValueError(
            f"provider-assembly rehearsal evidence is missing: {path}"
        )


def _file_sha256(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


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
            "provider-assembly rehearsal ID must be a safe path component"
        )


class _Clock:
    def __init__(self, *values: datetime) -> None:
        self.values = iter(values)

    def __call__(self) -> datetime:
        return next(self.values)
