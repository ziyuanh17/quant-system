"""Run actual-command rehearsals for finite supervised-provider dry-runs."""

import json
import os
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    FiniteSupervisedProviderCommandObservation,
    FiniteSupervisedProviderRehearsalReport,
    FiniteSupervisedProviderRehearsalScenario,
    FiniteSupervisedProviderRehearsalScenarioResult,
    FiniteSupervisedProviderStatus,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)
from quant.workflows.finite_supervised_provider import (
    finite_supervised_provider_manifest_for_paths,
    load_finite_supervised_provider_record,
    write_finite_supervised_provider_manifest,
)
from quant.workflows.supervised_provider_assembly import (
    load_supervised_provider_assembly_manifest,
)
from quant.workflows.supervised_provider_assembly_rehearsal import (
    load_and_verify_supervised_provider_assembly_rehearsal,
    run_supervised_provider_assembly_local_rehearsal,
)
from quant.workflows.supervised_provider_operator import (
    write_supervised_provider_operator_request,
)

FINITE_SUPERVISED_PROVIDER_REHEARSAL_POLICY = (
    "finite_supervised_provider_actual_command_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_finite_supervised_provider_command_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    quant_executable_path: Path,
    evaluated_at: datetime,
) -> FiniteSupervisedProviderRehearsalReport:
    """Run finite supervised-provider command scenarios and persist proof."""
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
        lock_name=f"finite-supervised-provider-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = (
                FiniteSupervisedProviderRehearsalReport.model_validate_json(
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
                raise ValueError("finite rehearsal ID is bound to other inputs")
            _verify_report_evidence(report)
            return report

        prerequisite_root = output_root / "prerequisite"
        prerequisite = run_supervised_provider_assembly_local_rehearsal(
            rehearsal_id=f"{rehearsal_id}-assembly",
            output_root=prerequisite_root,
            evaluated_at=evaluated_at,
        )
        prerequisite_path = (
            prerequisite_root / "reports" / f"{rehearsal_id}-assembly.json"
        )
        scenarios_root = output_root / "scenarios"
        scenarios = (
            _exact_list_completion(
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
            _preflight_rejection(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _stop_on_block(
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
        report = FiniteSupervisedProviderRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=FINITE_SUPERVISED_PROVIDER_REHEARSAL_POLICY,
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
                "all actual-command finite supervised-provider scenarios passed"
                if passed
                else "one or more finite supervised-provider scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_finite_supervised_provider_rehearsal(
    report_path: Path,
) -> FiniteSupervisedProviderRehearsalReport:
    """Load and verify one finite supervised-provider command rehearsal."""
    report = FiniteSupervisedProviderRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _exact_list_completion(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> FiniteSupervisedProviderRehearsalScenarioResult:
    scenario = FiniteSupervisedProviderRehearsalScenario.EXACT_LIST_COMPLETION
    scenario_root = root / scenario.value
    manifest_path = _manifest(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, manifest_path
    )
    record_path = _loop_record_path(scenario_root, scenario)
    record = (
        load_finite_supervised_provider_record(record_path)
        if record_path.is_file()
        else None
    )
    passed = (
        observation.exit_code == 0
        and record is not None
        and record.status == FiniteSupervisedProviderStatus.COMPLETED
        and len(record.completed_request_ids) == 2
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        loop_record_paths=(record_path,) if record_path.is_file() else (),
        passed=passed,
        reason="actual finite command completed an exact two-request list",
    )


def _restart_reuse(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> FiniteSupervisedProviderRehearsalScenarioResult:
    scenario = FiniteSupervisedProviderRehearsalScenario.RESTART_REUSE
    scenario_root = root / scenario.value
    manifest_path = _manifest(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    first = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, manifest_path
    )
    record_path = _loop_record_path(scenario_root, scenario)
    first_digest = _file_sha256(record_path) if record_path.is_file() else ""
    second = _run_command(
        scenario_root, scenario, 2, executable, executable_digest, manifest_path
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
        loop_record_paths=(record_path,) if record_path.is_file() else (),
        passed=passed,
        reason="actual finite command restart reused one durable summary",
    )


def _preflight_rejection(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> FiniteSupervisedProviderRehearsalScenarioResult:
    scenario = FiniteSupervisedProviderRehearsalScenario.PREFLIGHT_REJECTION
    scenario_root = root / scenario.value
    manifest_path = _manifest(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    second_request = sorted((scenario_root / "reviewed").glob("*.json"))[1]
    second_request.write_text(second_request.read_text() + " ")
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, manifest_path
    )
    output = observation.stdout + observation.stderr
    passed = (
        observation.exit_code != 0
        and "request hash does not match" in output
        and not _loop_record_path(scenario_root, scenario).exists()
        and not (scenario_root / "request-outputs").exists()
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        passed=passed,
        reason="actual finite command rejected changed request before running",
    )


def _stop_on_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> FiniteSupervisedProviderRehearsalScenarioResult:
    scenario = FiniteSupervisedProviderRehearsalScenario.STOP_ON_BLOCK
    scenario_root = root / scenario.value
    manifest_path = _manifest(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "stale_target_rejected", "restart_reuse"),
        now,
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, manifest_path
    )
    record_path = _loop_record_path(scenario_root, scenario)
    record = (
        load_finite_supervised_provider_record(record_path)
        if record_path.is_file()
        else None
    )
    passed = (
        observation.exit_code != 0
        and record is not None
        and record.status == FiniteSupervisedProviderStatus.BLOCKED
        and len(record.completed_request_ids) == 1
        and record.blocked_request_id == "stale_target_rejected-stop_on_block"
        and not (
            scenario_root
            / "request-outputs"
            / "restart_reuse"
            / "operator-runs"
        ).exists()
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        loop_record_paths=(record_path,) if record_path.is_file() else (),
        passed=passed,
        reason="actual finite command stopped before a later request",
    )


def _manifest(
    scenario_root: Path,
    scenario: FiniteSupervisedProviderRehearsalScenario,
    prerequisite_path: Path,
    prerequisite_scenarios: tuple[str, ...],
    now: datetime,
) -> Path:
    request_paths = tuple(
        _request(
            scenario_root,
            scenario,
            prerequisite_path,
            prerequisite_scenario,
            now,
        )
        for prerequisite_scenario in prerequisite_scenarios
    )
    manifest = finite_supervised_provider_manifest_for_paths(
        loop_id=f"{scenario.value}-loop",
        request_paths=request_paths,
        output_root=scenario_root / "loop-output",
        created_at=now,
        evidence_refs=("finite-command-rehearsal:no-network",),
    )
    return write_finite_supervised_provider_manifest(
        manifest, scenario_root / "manifests"
    )


def _request(
    scenario_root: Path,
    scenario: FiniteSupervisedProviderRehearsalScenario,
    prerequisite_path: Path,
    prerequisite_scenario: str,
    now: datetime,
) -> Path:
    prerequisite_root = prerequisite_path.parent.parent
    manifest_path = (
        prerequisite_root
        / "scenarios"
        / prerequisite_scenario
        / "output"
        / "assemblies"
        / f"{prerequisite_scenario}-assembly"
        / "manifest.json"
    )
    manifest = load_supervised_provider_assembly_manifest(manifest_path)
    authorization = load_autonomous_dry_run_authorization(
        Path(manifest.authorization_path)
    )
    request = SupervisedProviderOperatorRequest(
        request_id=f"{prerequisite_scenario}-{scenario.value}",
        assembly_manifest_path=str(manifest_path),
        assembly_manifest_sha256=_file_sha256(manifest_path),
        assembly_rehearsal_report_path=str(prerequisite_path),
        assembly_rehearsal_report_sha256=_file_sha256(prerequisite_path),
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
        output_root=str(
            scenario_root / "request-outputs" / prerequisite_scenario
        ),
        created_at=now,
        evidence_refs=("finite-command-rehearsal:no-network",),
    )
    return write_supervised_provider_operator_request(
        request, scenario_root / "reviewed"
    )


def _run_command(
    scenario_root: Path,
    scenario: FiniteSupervisedProviderRehearsalScenario,
    sequence: int,
    executable: Path,
    executable_digest: str,
    manifest_path: Path,
) -> FiniteSupervisedProviderCommandObservation:
    arguments = (
        "dry-run",
        "supervised-provider-finite",
        "--manifest-path",
        str(manifest_path),
    )
    completed = subprocess.run(
        [str(executable), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    observation = FiniteSupervisedProviderCommandObservation(
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
    scenario: FiniteSupervisedProviderRehearsalScenario,
    *,
    observations: tuple[FiniteSupervisedProviderCommandObservation, ...],
    passed: bool,
    reason: str,
    loop_record_paths: tuple[Path, ...] = (),
) -> FiniteSupervisedProviderRehearsalScenarioResult:
    observation_paths = tuple(
        scenario_root / "command-observations" / f"{index:06d}.json"
        for index in range(1, len(observations) + 1)
    )
    evidence_paths = tuple(
        path
        for path in sorted(scenario_root.rglob("*.json"))
        if path not in observation_paths and path not in loop_record_paths
    )
    return FiniteSupervisedProviderRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        command_observation_paths=tuple(
            str(path) for path in observation_paths
        ),
        command_observation_sha256s=tuple(
            _file_sha256(path) for path in observation_paths
        ),
        loop_record_paths=tuple(str(path) for path in loop_record_paths),
        loop_record_sha256s=tuple(
            _file_sha256(path) for path in loop_record_paths
        ),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        evidence_sha256s=tuple(_file_sha256(path) for path in evidence_paths),
        reason=reason,
    )


def _loop_record_path(
    scenario_root: Path, scenario: FiniteSupervisedProviderRehearsalScenario
) -> Path:
    return (
        scenario_root / "loop-output" / "loops" / f"{scenario.value}-loop.json"
    )


def _verify_report_evidence(
    report: FiniteSupervisedProviderRehearsalReport,
) -> None:
    root = Path(report.evidence_root)
    if _file_sha256(Path(report.executable_path)) != report.executable_sha256:
        raise ValueError("finite rehearsal executable changed")
    for path_value, digest in zip(
        report.source_paths, report.source_sha256s, strict=True
    ):
        _require_hash(Path(path_value), digest)
    _require_hash(
        Path(report.prerequisite_report_path),
        report.prerequisite_report_sha256,
    )
    prerequisite = load_and_verify_supervised_provider_assembly_rehearsal(
        Path(report.prerequisite_report_path)
    )
    if not prerequisite.passed:
        raise ValueError("finite rehearsal prerequisite did not pass")
    if _prohibited_artifact_paths(root) != report.prohibited_artifact_paths:
        raise ValueError("finite rehearsal prohibited evidence changed")
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
                FiniteSupervisedProviderCommandObservation.model_validate_json(
                    path.read_text()
                )
            )
            if (
                observation.scenario != scenario.scenario
                or observation.executable_path != report.executable_path
                or observation.executable_sha256 != report.executable_sha256
            ):
                raise ValueError("finite rehearsal command evidence changed")
            observations.append(observation)
        _verify_command_outcome(scenario, observations)
        for path_value, digest in zip(
            scenario.loop_record_paths,
            scenario.loop_record_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            load_finite_supervised_provider_record(path)
        for path_value, digest in zip(
            scenario.evidence_paths, scenario.evidence_sha256s, strict=True
        ):
            _require_hash(Path(path_value), digest)


def _verify_command_outcome(
    scenario: FiniteSupervisedProviderRehearsalScenarioResult,
    observations: list[FiniteSupervisedProviderCommandObservation],
) -> None:
    successful = {
        FiniteSupervisedProviderRehearsalScenario.EXACT_LIST_COMPLETION,
        FiniteSupervisedProviderRehearsalScenario.RESTART_REUSE,
    }
    if (scenario.scenario in successful) != all(
        item.exit_code == 0 for item in observations
    ):
        raise ValueError("finite rehearsal command outcome changed")
    if (
        scenario.scenario
        == FiniteSupervisedProviderRehearsalScenario.RESTART_REUSE
        and len(observations) != 2
    ):
        raise ValueError("finite rehearsal restart evidence changed")
    if (
        scenario.scenario
        != FiniteSupervisedProviderRehearsalScenario.RESTART_REUSE
        and len(observations) != 1
    ):
        raise ValueError("finite rehearsal command evidence changed")
    output = "".join(item.stdout + item.stderr for item in observations)
    if (
        scenario.scenario
        == FiniteSupervisedProviderRehearsalScenario.PREFLIGHT_REJECTION
        and "request hash does not match" not in output
    ):
        raise ValueError("finite rehearsal preflight rejection changed")
    if (
        scenario.scenario
        == FiniteSupervisedProviderRehearsalScenario.STOP_ON_BLOCK
        and "Status: blocked" not in output
    ):
        raise ValueError("finite rehearsal stop-on-block evidence changed")
    expects_record = scenario.scenario in {
        *successful,
        FiniteSupervisedProviderRehearsalScenario.STOP_ON_BLOCK,
    }
    if expects_record != (len(scenario.loop_record_paths) == 1):
        raise ValueError("finite rehearsal result evidence changed")
    if (
        scenario.scenario
        == FiniteSupervisedProviderRehearsalScenario.STOP_ON_BLOCK
        and len(scenario.loop_record_paths) != 1
    ):
        raise ValueError("finite rehearsal blocked record evidence changed")


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or _file_sha256(path) != expected:
        raise ValueError(f"finite rehearsal evidence changed: {path}")


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
        raise ValueError("finite rehearsal ID must be a safe path component")
