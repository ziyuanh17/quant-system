"""Run and verify actual-command supervised-provider dry-run rehearsals."""

import json
import os
import shutil
import subprocess
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    SupervisedProviderOperatorCommandObservation,
    SupervisedProviderOperatorRehearsalReport,
    SupervisedProviderOperatorRehearsalScenario,
    SupervisedProviderOperatorRehearsalScenarioResult,
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
    load_and_verify_supervised_provider_assembly_rehearsal,
    run_supervised_provider_assembly_local_rehearsal,
)
from quant.workflows.supervised_provider_operator import (
    load_supervised_provider_operator_record,
    write_supervised_provider_operator_request,
)

SUPERVISED_PROVIDER_OPERATOR_REHEARSAL_POLICY = (
    "supervised_provider_operator_actual_command_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_supervised_provider_operator_command_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    quant_executable_path: Path,
    evaluated_at: datetime,
) -> SupervisedProviderOperatorRehearsalReport:
    """Run four isolated actual-command scenarios and persist proof."""
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
        lock_name=f"supervised-provider-operator-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = (
                SupervisedProviderOperatorRehearsalReport.model_validate_json(
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
                    "operator rehearsal ID is bound to other inputs"
                )
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
            _fresh_completion(
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
            _stale_input_block(
                scenarios_root,
                executable,
                executable_digest,
                prerequisite_path,
                evaluated_at,
            ),
            _tampered_input_block(
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
        report = SupervisedProviderOperatorRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=(
                SUPERVISED_PROVIDER_OPERATOR_REHEARSAL_POLICY
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
                "all actual-command supervised-provider scenarios passed"
                if passed
                else "one or more supervised-provider command scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_supervised_provider_operator_rehearsal(
    report_path: Path,
) -> SupervisedProviderOperatorRehearsalReport:
    """Load an actual-command operator rehearsal and verify all evidence."""
    report = SupervisedProviderOperatorRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _fresh_completion(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderOperatorRehearsalScenarioResult:
    scenario = SupervisedProviderOperatorRehearsalScenario.FRESH_COMPLETION
    scenario_root = root / scenario.value
    request_path = _request(
        scenario_root, scenario, prerequisite_path, "successful_assembly", now
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _operator_record_path(scenario_root, scenario)
    passed = observation.exit_code == 0 and record_path.is_file()
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        operator_record_paths=(record_path,) if record_path.is_file() else (),
        passed=passed,
        reason="fresh reviewed request completed one actual operator command",
    )


def _restart_reuse(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderOperatorRehearsalScenarioResult:
    scenario = SupervisedProviderOperatorRehearsalScenario.RESTART_REUSE
    scenario_root = root / scenario.value
    request_path = _request(
        scenario_root, scenario, prerequisite_path, "successful_assembly", now
    )
    first = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    record_path = _operator_record_path(scenario_root, scenario)
    first_digest = _file_sha256(record_path) if record_path.is_file() else ""
    second = _run_command(
        scenario_root, scenario, 2, executable, executable_digest, request_path
    )
    passed = (
        first.exit_code == second.exit_code == 0
        and record_path.is_file()
        and _file_sha256(record_path) == first_digest
        and len(tuple((record_path.parent).glob("*.json"))) == 1
    )
    return _result(
        scenario_root,
        scenario,
        observations=(first, second),
        operator_record_paths=(record_path,) if record_path.is_file() else (),
        passed=passed,
        reason="restarting the actual command reused one durable result",
    )


def _stale_input_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderOperatorRehearsalScenarioResult:
    scenario = SupervisedProviderOperatorRehearsalScenario.STALE_INPUT_BLOCK
    scenario_root = root / scenario.value
    request_path = _request(
        scenario_root, scenario, prerequisite_path, "stale_target_rejected", now
    )
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    output = observation.stdout + observation.stderr
    passed = (
        observation.exit_code != 0
        and "do not aggregate actively" in output
        and not _operator_record_path(scenario_root, scenario).exists()
        and not (scenario_root / "operator-output" / "supervisor").exists()
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        passed=passed,
        reason="stale target evidence blocked the actual command",
    )


def _tampered_input_block(
    root: Path,
    executable: Path,
    executable_digest: str,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderOperatorRehearsalScenarioResult:
    scenario = SupervisedProviderOperatorRehearsalScenario.TAMPERED_INPUT_BLOCK
    scenario_root = root / scenario.value
    request_path = _request(
        scenario_root,
        scenario,
        prerequisite_path,
        "successful_assembly",
        now,
        copy_manifest=True,
    )
    request = SupervisedProviderOperatorRequest.model_validate_json(
        request_path.read_text()
    )
    manifest_path = Path(request.assembly_manifest_path)
    manifest_path.write_text(manifest_path.read_text() + " ")
    observation = _run_command(
        scenario_root, scenario, 1, executable, executable_digest, request_path
    )
    output = observation.stdout + observation.stderr
    passed = (
        observation.exit_code != 0
        and "input hash does not match" in output
        and not _operator_record_path(scenario_root, scenario).exists()
        and not (scenario_root / "operator-output" / "assembly").exists()
        and not (scenario_root / "operator-output" / "supervisor").exists()
    )
    return _result(
        scenario_root,
        scenario,
        observations=(observation,),
        passed=passed,
        reason="changed reviewed manifest blocked the actual command",
    )


def _request(
    scenario_root: Path,
    scenario: SupervisedProviderOperatorRehearsalScenario,
    prerequisite_path: Path,
    prerequisite_scenario: str,
    now: datetime,
    *,
    copy_manifest: bool = False,
) -> Path:
    prerequisite_root = prerequisite_path.parent.parent
    source_manifest = (
        prerequisite_root
        / "scenarios"
        / prerequisite_scenario
        / "output"
        / "assemblies"
        / f"{prerequisite_scenario}-assembly"
        / "manifest.json"
    )
    manifest_path = source_manifest
    if copy_manifest:
        manifest_path = scenario_root / "reviewed" / "manifest.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_manifest, manifest_path)
    manifest = load_supervised_provider_assembly_manifest(manifest_path)
    authorization = load_autonomous_dry_run_authorization(
        Path(manifest.authorization_path)
    )
    request = SupervisedProviderOperatorRequest(
        request_id=f"{scenario.value}-request",
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
        output_root=str(scenario_root / "operator-output"),
        created_at=now,
        evidence_refs=("actual-command-rehearsal:no-network",),
    )
    return write_supervised_provider_operator_request(
        request, scenario_root / "reviewed"
    )


def _run_command(
    scenario_root: Path,
    scenario: SupervisedProviderOperatorRehearsalScenario,
    sequence: int,
    executable: Path,
    executable_digest: str,
    request_path: Path,
) -> SupervisedProviderOperatorCommandObservation:
    arguments = (
        "dry-run",
        "supervised-provider",
        "--request-path",
        str(request_path),
    )
    completed = subprocess.run(
        [str(executable), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    observation = SupervisedProviderOperatorCommandObservation(
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
    scenario: SupervisedProviderOperatorRehearsalScenario,
    *,
    observations: tuple[SupervisedProviderOperatorCommandObservation, ...],
    passed: bool,
    reason: str,
    operator_record_paths: tuple[Path, ...] = (),
) -> SupervisedProviderOperatorRehearsalScenarioResult:
    observation_paths = tuple(
        scenario_root / "command-observations" / f"{index:06d}.json"
        for index in range(1, len(observations) + 1)
    )
    evidence_paths = tuple(
        path
        for path in sorted(scenario_root.rglob("*.json"))
        if path not in observation_paths and path not in operator_record_paths
    )
    return SupervisedProviderOperatorRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        command_observation_paths=tuple(
            str(path) for path in observation_paths
        ),
        command_observation_sha256s=tuple(
            _file_sha256(path) for path in observation_paths
        ),
        operator_record_paths=tuple(
            str(path) for path in operator_record_paths
        ),
        operator_record_sha256s=tuple(
            _file_sha256(path) for path in operator_record_paths
        ),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        evidence_sha256s=tuple(_file_sha256(path) for path in evidence_paths),
        reason=reason,
    )


def _operator_record_path(
    scenario_root: Path,
    scenario: SupervisedProviderOperatorRehearsalScenario,
) -> Path:
    return (
        scenario_root
        / "operator-output"
        / "operator-runs"
        / f"{scenario.value}-request.json"
    )


def _verify_report_evidence(
    report: SupervisedProviderOperatorRehearsalReport,
) -> None:
    root = Path(report.evidence_root)
    if _file_sha256(Path(report.executable_path)) != report.executable_sha256:
        raise ValueError("operator rehearsal executable changed")
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
        raise ValueError("operator rehearsal prerequisite did not pass")
    if _prohibited_artifact_paths(root) != report.prohibited_artifact_paths:
        raise ValueError("operator rehearsal prohibited evidence changed")
    for scenario in report.scenarios:
        observations: list[SupervisedProviderOperatorCommandObservation] = []
        for path_value, digest in zip(
            scenario.command_observation_paths,
            scenario.command_observation_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            observation = (
                SupervisedProviderOperatorCommandObservation.model_validate_json(
                    path.read_text()
                )
            )
            if (
                observation.scenario != scenario.scenario
                or observation.executable_path != report.executable_path
                or observation.executable_sha256 != report.executable_sha256
            ):
                raise ValueError("operator rehearsal command evidence changed")
            observations.append(observation)
        expected_success = scenario.scenario in {
            SupervisedProviderOperatorRehearsalScenario.FRESH_COMPLETION,
            SupervisedProviderOperatorRehearsalScenario.RESTART_REUSE,
        }
        if expected_success != all(
            item.exit_code == 0 for item in observations
        ):
            raise ValueError("operator rehearsal command outcome changed")
        if (
            scenario.scenario
            == SupervisedProviderOperatorRehearsalScenario.RESTART_REUSE
            and len(observations) != 2
        ):
            raise ValueError("operator rehearsal restart evidence changed")
        if (
            scenario.scenario
            != SupervisedProviderOperatorRehearsalScenario.RESTART_REUSE
            and len(observations) != 1
        ):
            raise ValueError("operator rehearsal command evidence changed")
        if expected_success != (len(scenario.operator_record_paths) == 1):
            raise ValueError("operator rehearsal result evidence changed")
        output = "".join(item.stdout + item.stderr for item in observations)
        if (
            scenario.scenario
            == SupervisedProviderOperatorRehearsalScenario.STALE_INPUT_BLOCK
            and "do not aggregate actively" not in output
        ):
            raise ValueError("operator rehearsal stale rejection changed")
        if (
            scenario.scenario
            == SupervisedProviderOperatorRehearsalScenario.TAMPERED_INPUT_BLOCK
            and "input hash does not match" not in output
        ):
            raise ValueError("operator rehearsal tamper rejection changed")
        for path_value, digest in zip(
            scenario.operator_record_paths,
            scenario.operator_record_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            load_supervised_provider_operator_record(path)
        for path_value, digest in zip(
            scenario.evidence_paths, scenario.evidence_sha256s, strict=True
        ):
            _require_hash(Path(path_value), digest)


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or _file_sha256(path) != expected:
        raise ValueError(f"operator rehearsal evidence changed: {path}")


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
        raise ValueError("operator rehearsal ID must be a safe path component")
