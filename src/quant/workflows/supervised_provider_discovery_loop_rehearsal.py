"""Run actual-command rehearsals for discovery-to-loop composition."""

import json
import os
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    SupervisedProviderDiscoveryLoopCommandObservation,
    SupervisedProviderDiscoveryLoopOperatorRecord,
    SupervisedProviderDiscoveryLoopOperatorRequest,
    SupervisedProviderDiscoveryLoopRehearsalReport,
    SupervisedProviderDiscoveryLoopRehearsalScenario,
    SupervisedProviderDiscoveryLoopRehearsalScenarioResult,
    SupervisedProviderDiscoveryLoopStatus,
    SupervisedProviderDiscoveryOperatorRequest,
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)
from quant.workflows.supervised_provider_assembly import (
    load_supervised_provider_assembly_manifest,
)
from quant.workflows.supervised_provider_assembly_rehearsal import (
    run_supervised_provider_assembly_local_rehearsal,
)
from quant.workflows.supervised_provider_discovery_loop_operator import (
    load_supervised_provider_discovery_loop_operator_record,
    write_supervised_provider_discovery_loop_operator_request,
)
from quant.workflows.supervised_provider_discovery_operator import (
    write_supervised_provider_discovery_operator_request,
)
from quant.workflows.supervised_provider_discovery_operator_rehearsal import (
    SUPERVISED_PROVIDER_DISCOVERY_OPERATOR_REHEARSAL_POLICY,
    load_and_verify_supervised_provider_discovery_operator_rehearsal,
    run_supervised_provider_discovery_operator_command_rehearsal,
)
from quant.workflows.supervised_provider_discovery_rehearsal import (
    run_supervised_provider_discovery_handoff_rehearsal,
)
from quant.workflows.supervised_provider_operator import (
    write_supervised_provider_operator_request,
)

SUPERVISED_PROVIDER_DISCOVERY_LOOP_REHEARSAL_POLICY = (
    "supervised_provider_discovery_loop_actual_command_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_supervised_provider_discovery_loop_command_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    quant_executable_path: Path,
    evaluated_at: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalReport:
    """Run discovery-to-loop command scenarios and persist proof."""
    _require_safe_id(rehearsal_id)
    executable = quant_executable_path.resolve()
    executable_digest = _file_sha256(executable)
    source_paths = tuple(
        path
        for path in sorted(Path(__file__).parents[1].rglob("*.py"))
        if path.is_file()
    )
    source_sha256s = tuple(_file_sha256(path) for path in source_paths)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"discovery-loop-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = (
                SupervisedProviderDiscoveryLoopRehearsalReport.model_validate_json(
                    report_path.read_text()
                )
            )
            if (
                report.evaluated_at != evaluated_at
                or report.executable_path != str(executable)
                or report.executable_sha256 != executable_digest
                or report.source_paths
                != tuple(str(path) for path in source_paths)
                or report.source_sha256s != source_sha256s
            ):
                raise ValueError(
                    "discovery-loop rehearsal ID is bound to other inputs"
                )
            _verify_report_evidence(report)
            return report

        prerequisite_root = output_root / "prerequisite"
        prerequisite = (
            run_supervised_provider_discovery_operator_command_rehearsal(
                rehearsal_id=f"{rehearsal_id}-operator",
                output_root=prerequisite_root,
                quant_executable_path=executable,
                evaluated_at=evaluated_at,
            )
        )
        prerequisite_path = (
            prerequisite_root / "reports" / f"{rehearsal_id}-operator.json"
        )
        scenarios_root = output_root / "scenarios"
        scenarios = (
            _exact_completion(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _restart_reuse(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _discovery_block(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _loop_block(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _tampered_rehearsal_block(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
        )
        prohibited = _prohibited_artifact_paths(output_root)
        passed = (
            prerequisite.passed
            and all(item.passed for item in scenarios)
            and not prohibited
        )
        report = SupervisedProviderDiscoveryLoopRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=(
                SUPERVISED_PROVIDER_DISCOVERY_LOOP_REHEARSAL_POLICY
            ),
            evidence_root=str(output_root),
            executable_path=str(executable),
            executable_sha256=executable_digest,
            source_paths=tuple(str(path) for path in source_paths),
            source_sha256s=source_sha256s,
            prerequisite_report_path=str(prerequisite_path),
            prerequisite_report_sha256=_file_sha256(prerequisite_path),
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            prohibited_artifact_paths=prohibited,
            reason=(
                "all actual-command discovery-loop scenarios passed"
                if passed
                else "one or more discovery-loop scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_supervised_provider_discovery_loop_rehearsal(
    report_path: Path,
) -> SupervisedProviderDiscoveryLoopRehearsalReport:
    """Load and verify one discovery-to-loop command rehearsal."""
    report = SupervisedProviderDiscoveryLoopRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _exact_completion(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryLoopRehearsalScenario.EXACT_COMPLETION
    scenario_root = root / scenario.value
    request_path = _composition_request(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _composition_record_path(scenario_root, scenario)
    record = _load_record_if_present(record_path)
    passed = (
        observation.exit_code == 0
        and record is not None
        and record.status == SupervisedProviderDiscoveryLoopStatus.COMPLETED
        and record.finite_loop_record_path is not None
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        composition_record_paths=(
            (record_path,) if record_path.is_file() else ()
        ),
        passed=passed,
        reason="actual discovery-loop command completed exact discovered work",
    )


def _restart_reuse(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryLoopRehearsalScenario.RESTART_REUSE
    scenario_root = root / scenario.value
    request_path = _composition_request(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    first = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _composition_record_path(scenario_root, scenario)
    first_digest = _file_sha256(record_path) if record_path.is_file() else ""
    second = _run_command(
        scenario_root, scenario, 2, executable, executable_digest, request_path
    )
    passed = (
        first.exit_code == second.exit_code == 0
        and record_path.is_file()
        and _file_sha256(record_path) == first_digest
        and len(tuple(record_path.parent.glob("*.json"))) == 1
    )
    return _result(
        scenario_root,
        scenario,
        observations=(first, second),
        composition_record_paths=(
            (record_path,) if record_path.is_file() else ()
        ),
        passed=passed,
        reason="actual discovery-loop command restart reused one record",
    )


def _discovery_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryLoopRehearsalScenario.DISCOVERY_BLOCK
    scenario_root = root / scenario.value
    request_path = _composition_request(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
        maximum_requests=1,
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _composition_record_path(scenario_root, scenario)
    record = _load_record_if_present(record_path)
    passed = (
        observation.exit_code != 0
        and record is not None
        and record.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED
        and record.finite_loop_record_path is None
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        composition_record_paths=(
            (record_path,) if record_path.is_file() else ()
        ),
        passed=passed,
        reason="actual discovery-loop command blocked before finite loop",
    )


def _loop_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryLoopRehearsalScenario.LOOP_BLOCK
    scenario_root = root / scenario.value
    request_path = _composition_request(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "stale_target_rejected", "restart_reuse"),
        now,
        maximum_requests=3,
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _composition_record_path(scenario_root, scenario)
    record = _load_record_if_present(record_path)
    passed = (
        observation.exit_code != 0
        and record is not None
        and record.status == SupervisedProviderDiscoveryLoopStatus.BLOCKED
        and record.finite_loop_record_path is not None
        and "finite loop blocked" in record.reason
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        composition_record_paths=(
            (record_path,) if record_path.is_file() else ()
        ),
        passed=passed,
        reason="actual discovery-loop command surfaced finite loop block",
    )


def _tampered_rehearsal_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    scenario = (
        SupervisedProviderDiscoveryLoopRehearsalScenario.TAMPERED_REHEARSAL_BLOCK
    )
    scenario_root = root / scenario.value
    request_path = _composition_request(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
        copy_rehearsal=True,
    )
    request = (
        SupervisedProviderDiscoveryLoopOperatorRequest.model_validate_json(
            request_path.read_text()
        )
    )
    path = Path(request.discovery_operator_rehearsal_report_path)
    path.write_text(path.read_text() + " ")
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    output = observation.stdout + observation.stderr
    passed = (
        observation.exit_code != 0
        and "hash does not match" in output
        and not _composition_record_path(scenario_root, scenario).exists()
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        passed=passed,
        reason="actual discovery-loop command rejected changed rehearsal",
    )


def _composition_request(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
    prerequisite_path: Path,
    request_scenarios: tuple[str, ...],
    now: datetime,
    *,
    maximum_requests: int = 2,
    copy_rehearsal: bool = False,
) -> Path:
    discovery_request_path = _discovery_operator_request(
        scenario_root, scenario, request_scenarios, maximum_requests, now
    )
    rehearsal_path = prerequisite_path
    if copy_rehearsal:
        rehearsal_path = scenario_root / "reviewed" / "operator-report.json"
        rehearsal_path.parent.mkdir(parents=True, exist_ok=True)
        rehearsal_path.write_bytes(prerequisite_path.read_bytes())
    request = SupervisedProviderDiscoveryLoopOperatorRequest(
        request_id=f"{scenario.value}-request",
        discovery_operator_request_path=str(discovery_request_path),
        discovery_operator_request_sha256=_file_sha256(
            discovery_request_path
        ),
        discovery_operator_rehearsal_report_path=str(rehearsal_path),
        discovery_operator_rehearsal_report_sha256=_file_sha256(
            rehearsal_path
        ),
        output_root=str(scenario_root / "composition-output"),
        created_at=now,
        evidence_refs=("discovery-loop-command-rehearsal:no-network",),
    )
    return write_supervised_provider_discovery_loop_operator_request(
        request, scenario_root / "reviewed"
    )


def _discovery_operator_request(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
    request_scenarios: tuple[str, ...],
    maximum_requests: int,
    now: datetime,
) -> Path:
    handoff_root = scenario_root / "discovery-handoff"
    run_supervised_provider_discovery_handoff_rehearsal(
        rehearsal_id=f"{scenario.value}-handoff",
        output_root=handoff_root,
        evaluated_at=now,
    )
    handoff_path = handoff_root / "reports" / f"{scenario.value}-handoff.json"
    reviewed, _ = _reviewed_requests(
        scenario_root, scenario, request_scenarios, now
    )
    request = SupervisedProviderDiscoveryOperatorRequest(
        request_id=f"{scenario.value}-discovery-request",
        discovery_policy=SupervisedProviderDiscoveryPolicy(
            discovery_id=f"{scenario.value}-discovery",
            discovery_policy_version="supervised_provider_discovery_v1",
            request_directory=str(reviewed),
            maximum_requests=maximum_requests,
            finite_loop_id=f"{scenario.value}-loop",
            finite_output_root=str(scenario_root / "finite-output"),
            created_at=now,
            evidence_refs=("discovery-loop-command-rehearsal:no-network",),
        ),
        output_root=str(scenario_root / "discovery-output"),
        discovery_rehearsal_report_path=str(handoff_path),
        discovery_rehearsal_report_sha256=_file_sha256(handoff_path),
        created_at=now,
        evidence_refs=("discovery-loop-command-rehearsal:no-network",),
    )
    return write_supervised_provider_discovery_operator_request(
        request, scenario_root / "reviewed-discovery"
    )


def _reviewed_requests(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
    request_scenarios: tuple[str, ...],
    now: datetime,
) -> tuple[Path, tuple[SupervisedProviderOperatorRequest, ...]]:
    prerequisite_root = scenario_root / "assembly-prerequisite"
    run_supervised_provider_assembly_local_rehearsal(
        rehearsal_id=f"{scenario.value}-assembly",
        output_root=prerequisite_root,
        evaluated_at=now,
    )
    report_path = (
        prerequisite_root / "reports" / f"{scenario.value}-assembly.json"
    )
    reviewed = scenario_root / "reviewed-requests"
    requests = tuple(
        _request(scenario_root, prerequisite_root, report_path, item, now)
        for item in request_scenarios
    )
    for request in requests:
        write_supervised_provider_operator_request(request, reviewed)
    return reviewed, requests


def _request(
    scenario_root: Path,
    prerequisite_root: Path,
    report_path: Path,
    scenario_name: str,
    now: datetime,
) -> SupervisedProviderOperatorRequest:
    manifest_path = (
        prerequisite_root
        / "scenarios"
        / scenario_name
        / "output"
        / "assemblies"
        / f"{scenario_name}-assembly"
        / "manifest.json"
    )
    manifest = load_supervised_provider_assembly_manifest(manifest_path)
    authorization = load_autonomous_dry_run_authorization(
        Path(manifest.authorization_path)
    )
    return SupervisedProviderOperatorRequest(
        request_id=f"{scenario_name}-discovery-loop-command-request",
        assembly_manifest_path=str(manifest_path),
        assembly_manifest_sha256=_file_sha256(manifest_path),
        assembly_rehearsal_report_path=str(report_path),
        assembly_rehearsal_report_sha256=_file_sha256(report_path),
        service_policy=SupervisedDryRunServicePolicy(
            service_id=manifest.service_id,
            policy_version="bounded_supervised_dry_run_v1",
            authorization_id=authorization.authorization_id,
            authorization_revision=authorization.revision,
            maximum_cycles=1,
            interval_seconds=0,
            maximum_runtime_seconds=60,
            created_at=now,
        ),
        output_root=str(scenario_root / "request-outputs" / scenario_name),
        created_at=now,
        evidence_refs=("discovery-loop-command-rehearsal:no-network",),
    )


def _run_command(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
    sequence: int,
    executable: Path,
    executable_digest: str,
    request_path: Path,
) -> SupervisedProviderDiscoveryLoopCommandObservation:
    arguments = (
        "dry-run",
        "supervised-provider-discover-finite",
        "--request-path",
        str(request_path),
    )
    completed = subprocess.run(
        [str(executable), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    observation = SupervisedProviderDiscoveryLoopCommandObservation(
        observation_id=f"{scenario.value}:{sequence}",
        scenario=scenario,
        sequence=sequence,
        executable_path=str(executable),
        executable_sha256=executable_digest,
        arguments=arguments,
        exit_code=completed.returncode,
        stdout=completed.stdout,
        stderr=completed.stderr,
        observed_at=datetime.now(UTC),
    )
    _write_model_exclusive(
        scenario_root / "command-observations" / f"{sequence:06d}.json",
        observation,
    )
    return observation


def _result(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
    *,
    observations: tuple[SupervisedProviderDiscoveryLoopCommandObservation, ...],
    passed: bool,
    reason: str,
    composition_record_paths: tuple[Path, ...] = (),
) -> SupervisedProviderDiscoveryLoopRehearsalScenarioResult:
    observation_paths = tuple(
        scenario_root / "command-observations" / f"{index:06d}.json"
        for index in range(1, len(observations) + 1)
    )
    evidence_paths = tuple(
        path
        for path in sorted(scenario_root.rglob("*.json"))
        if path not in observation_paths
        and path not in composition_record_paths
    )
    return SupervisedProviderDiscoveryLoopRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        command_observation_paths=tuple(
            str(path) for path in observation_paths
        ),
        command_observation_sha256s=tuple(
            _file_sha256(path) for path in observation_paths
        ),
        composition_record_paths=tuple(
            str(path) for path in composition_record_paths
        ),
        composition_record_sha256s=tuple(
            _file_sha256(path) for path in composition_record_paths
        ),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        evidence_sha256s=tuple(_file_sha256(path) for path in evidence_paths),
        reason=reason,
    )


def _composition_record_path(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenario,
) -> Path:
    return (
        scenario_root
        / "composition-output"
        / "operator-runs"
        / f"{scenario.value}-request.json"
    )


def _load_record_if_present(
    path: Path,
) -> SupervisedProviderDiscoveryLoopOperatorRecord | None:
    return (
        load_supervised_provider_discovery_loop_operator_record(path)
        if path.is_file()
        else None
    )


def _verify_report_evidence(
    report: SupervisedProviderDiscoveryLoopRehearsalReport,
) -> None:
    root = Path(report.evidence_root)
    if _file_sha256(Path(report.executable_path)) != report.executable_sha256:
        raise ValueError("discovery-loop executable changed")
    for path_value, digest in zip(
        report.source_paths, report.source_sha256s, strict=True
    ):
        _require_hash(Path(path_value), digest)
    _require_hash(
        Path(report.prerequisite_report_path),
        report.prerequisite_report_sha256,
    )
    prerequisite = (
        load_and_verify_supervised_provider_discovery_operator_rehearsal(
            Path(report.prerequisite_report_path)
        )
    )
    if (
        not prerequisite.passed
        or prerequisite.rehearsal_policy_version
        != SUPERVISED_PROVIDER_DISCOVERY_OPERATOR_REHEARSAL_POLICY
    ):
        raise ValueError("discovery-loop prerequisite did not pass")
    if _prohibited_artifact_paths(root) != report.prohibited_artifact_paths:
        raise ValueError("discovery-loop prohibited evidence changed")
    for scenario in report.scenarios:
        observations = []
        for path_value, digest in zip(
            scenario.command_observation_paths,
            scenario.command_observation_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            observation = (
                SupervisedProviderDiscoveryLoopCommandObservation.model_validate_json(
                    path.read_text()
                )
            )
            if (
                observation.scenario != scenario.scenario
                or observation.executable_path != report.executable_path
                or observation.executable_sha256 != report.executable_sha256
            ):
                raise ValueError("discovery-loop command evidence changed")
            observations.append(observation)
        _verify_command_outcome(scenario, observations)
        for path_value, digest in zip(
            scenario.composition_record_paths,
            scenario.composition_record_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            load_supervised_provider_discovery_loop_operator_record(path)
        for path_value, digest in zip(
            scenario.evidence_paths, scenario.evidence_sha256s, strict=True
        ):
            _require_hash(Path(path_value), digest)


def _verify_command_outcome(
    scenario: SupervisedProviderDiscoveryLoopRehearsalScenarioResult,
    observations: list[SupervisedProviderDiscoveryLoopCommandObservation],
) -> None:
    successful = {
        SupervisedProviderDiscoveryLoopRehearsalScenario.EXACT_COMPLETION,
        SupervisedProviderDiscoveryLoopRehearsalScenario.RESTART_REUSE,
    }
    if (scenario.scenario in successful) != all(
        item.exit_code == 0 for item in observations
    ):
        raise ValueError("discovery-loop command outcome changed")
    if (
        scenario.scenario
        == SupervisedProviderDiscoveryLoopRehearsalScenario.RESTART_REUSE
        and len(observations) != 2
    ):
        raise ValueError("discovery-loop restart evidence changed")
    if (
        scenario.scenario
        != SupervisedProviderDiscoveryLoopRehearsalScenario.RESTART_REUSE
        and len(observations) != 1
    ):
        raise ValueError("discovery-loop command evidence changed")
    output = "".join(item.stdout + item.stderr for item in observations)
    if (
        scenario.scenario
        == SupervisedProviderDiscoveryLoopRehearsalScenario.DISCOVERY_BLOCK
        and "Status: blocked" not in output
    ):
        raise ValueError("discovery-loop discovery block evidence changed")
    if (
        scenario.scenario
        == SupervisedProviderDiscoveryLoopRehearsalScenario.LOOP_BLOCK
        and "finite loop blocked" not in output
    ):
        raise ValueError("discovery-loop finite block evidence changed")
    if (
        scenario.scenario
        == (
            SupervisedProviderDiscoveryLoopRehearsalScenario
            .TAMPERED_REHEARSAL_BLOCK
        )
        and "hash does not match" not in output
    ):
        raise ValueError("discovery-loop tamper evidence changed")


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or _file_sha256(path) != expected:
        raise ValueError(f"discovery-loop evidence changed: {path}")


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
            "discovery-loop rehearsal ID must be a safe path component"
        )
