"""Run no-network rehearsals for supervised-provider request discovery."""

import json
import os
from datetime import datetime
from hashlib import sha256
from pathlib import Path

from pydantic import BaseModel

from quant.models.autonomous import SupervisedDryRunServicePolicy
from quant.models.operator import (
    FiniteSupervisedProviderStatus,
    SupervisedProviderDiscoveryPolicy,
    SupervisedProviderDiscoveryRehearsalReport,
    SupervisedProviderDiscoveryRehearsalScenario,
    SupervisedProviderDiscoveryRehearsalScenarioResult,
    SupervisedProviderDiscoveryResult,
    SupervisedProviderDiscoveryStatus,
    SupervisedProviderOperatorRequest,
)
from quant.operations import FileLock
from quant.workflows.autonomous_dry_run import (
    load_autonomous_dry_run_authorization,
)
from quant.workflows.finite_supervised_provider import (
    load_finite_supervised_provider_manifest,
    load_finite_supervised_provider_record,
    run_finite_supervised_provider_loop,
)
from quant.workflows.supervised_provider_assembly import (
    load_supervised_provider_assembly_manifest,
)
from quant.workflows.supervised_provider_assembly_rehearsal import (
    load_and_verify_supervised_provider_assembly_rehearsal,
    run_supervised_provider_assembly_local_rehearsal,
)
from quant.workflows.supervised_provider_discovery import (
    discover_supervised_provider_requests,
    load_supervised_provider_discovery_result,
    verify_supervised_provider_discovery_result,
)
from quant.workflows.supervised_provider_operator import (
    write_supervised_provider_operator_request,
)

SUPERVISED_PROVIDER_DISCOVERY_REHEARSAL_POLICY = (
    "supervised_provider_discovery_handoff_rehearsal_v1"
)
_PROHIBITED_DIRECTORY_NAMES = {"orders", "fills", "semantic-paper", "alpaca"}


def run_supervised_provider_discovery_handoff_rehearsal(
    *,
    rehearsal_id: str,
    output_root: Path,
    evaluated_at: datetime,
) -> SupervisedProviderDiscoveryRehearsalReport:
    """Run discovery handoff scenarios and persist immutable proof."""
    _require_safe_id(rehearsal_id)
    source_paths = tuple(
        path
        for path in sorted(Path(__file__).parents[1].rglob("*.py"))
        if path.is_file()
    )
    source_sha256s = tuple(_file_sha256(path) for path in source_paths)
    report_path = output_root / "reports" / f"{rehearsal_id}.json"
    with FileLock(
        path=output_root / "locks" / f"{rehearsal_id}.lock",
        lock_name=f"supervised-provider-discovery-rehearsal:{rehearsal_id}",
        stale_after_seconds=300,
    ):
        if report_path.exists():
            report = (
                SupervisedProviderDiscoveryRehearsalReport.model_validate_json(
                    report_path.read_text()
                )
            )
            if (
                report.evaluated_at != evaluated_at
                or report.source_paths
                != tuple(str(path) for path in source_paths)
                or report.source_sha256s != source_sha256s
            ):
                raise ValueError(
                    "provider discovery rehearsal ID is bound to other inputs"
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
            _discovery_to_loop(
                scenarios_root, prerequisite_path, evaluated_at
            ),
            _restart_reuse(scenarios_root, prerequisite_path, evaluated_at),
            _empty_directory_block(
                scenarios_root, prerequisite_path, evaluated_at
            ),
            _over_limit_block(
                scenarios_root, prerequisite_path, evaluated_at
            ),
            _changed_input_block(
                scenarios_root, prerequisite_path, evaluated_at
            ),
            _stop_on_block_handoff(
                scenarios_root, prerequisite_path, evaluated_at
            ),
        )
        prohibited = _prohibited_artifact_paths(output_root)
        passed = (
            prerequisite.passed
            and all(item.passed for item in scenarios)
            and not prohibited
        )
        report = SupervisedProviderDiscoveryRehearsalReport(
            rehearsal_id=rehearsal_id,
            rehearsal_policy_version=(
                SUPERVISED_PROVIDER_DISCOVERY_REHEARSAL_POLICY
            ),
            evidence_root=str(output_root),
            source_paths=tuple(str(path) for path in source_paths),
            source_sha256s=source_sha256s,
            prerequisite_report_path=str(prerequisite_path),
            prerequisite_report_sha256=_file_sha256(prerequisite_path),
            evaluated_at=evaluated_at,
            passed=passed,
            scenarios=scenarios,
            prohibited_artifact_paths=prohibited,
            reason=(
                "all supervised-provider discovery handoff scenarios passed"
                if passed
                else "one or more discovery handoff scenarios failed"
            ),
        )
        _write_model_exclusive(report_path, report)
        return report


def load_and_verify_supervised_provider_discovery_rehearsal(
    report_path: Path,
) -> SupervisedProviderDiscoveryRehearsalReport:
    """Load and verify one discovery handoff rehearsal report."""
    report = SupervisedProviderDiscoveryRehearsalReport.model_validate_json(
        report_path.read_text()
    )
    _verify_report_evidence(report)
    return report


def _discovery_to_loop(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryRehearsalScenario.DISCOVERY_TO_LOOP
    scenario_root = root / scenario.value
    _requests(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    result = _discover(scenario_root, scenario, now)
    record = run_finite_supervised_provider_loop(
        manifest_path=_completed_manifest_path(result),
        clock=lambda: now,
    )
    passed = (
        result.status == SupervisedProviderDiscoveryStatus.COMPLETED
        and record.status == FiniteSupervisedProviderStatus.COMPLETED
        and len(record.completed_request_ids) == 2
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        finite_manifest_paths=_manifest_paths(scenario_root),
        loop_record_paths=_loop_record_paths(scenario_root),
        passed=passed,
        reason="discovery produced a finite manifest consumed by the loop",
    )


def _restart_reuse(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryRehearsalScenario.RESTART_REUSE
    scenario_root = root / scenario.value
    _requests(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    first = _discover(scenario_root, scenario, now)
    first_digest = _file_sha256(_completed_manifest_path(first))
    second = _discover(scenario_root, scenario, now)
    record = run_finite_supervised_provider_loop(
        manifest_path=_completed_manifest_path(second),
        clock=lambda: now,
    )
    passed = (
        second == first
        and _file_sha256(_completed_manifest_path(second)) == first_digest
        and record.status == FiniteSupervisedProviderStatus.COMPLETED
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        finite_manifest_paths=_manifest_paths(scenario_root),
        loop_record_paths=_loop_record_paths(scenario_root),
        passed=passed,
        reason="discovery restart reused one verified result and manifest",
    )


def _empty_directory_block(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = (
        SupervisedProviderDiscoveryRehearsalScenario.EMPTY_DIRECTORY_BLOCK
    )
    scenario_root = root / scenario.value
    result = _discover(scenario_root, scenario, now, make_requests=False)
    passed = (
        result.status == SupervisedProviderDiscoveryStatus.BLOCKED
        and "request directory is missing" in str(result.blocked_reason)
        and not _manifest_paths(scenario_root)
        and not _loop_record_paths(scenario_root)
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        passed=passed,
        reason="discovery blocked an absent reviewed request directory",
    )


def _over_limit_block(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryRehearsalScenario.OVER_LIMIT_BLOCK
    scenario_root = root / scenario.value
    _requests(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    result = _discover(scenario_root, scenario, now, maximum_requests=1)
    passed = (
        result.status == SupervisedProviderDiscoveryStatus.BLOCKED
        and "request limit exceeded" in str(result.blocked_reason)
        and not _manifest_paths(scenario_root)
        and not _loop_record_paths(scenario_root)
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        passed=passed,
        reason="discovery blocked more reviewed requests than policy allowed",
    )


def _changed_input_block(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = SupervisedProviderDiscoveryRehearsalScenario.CHANGED_INPUT_BLOCK
    scenario_root = root / scenario.value
    requests = _requests(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "restart_reuse"),
        now,
    )
    manifest_path = Path(requests[1].assembly_manifest_path)
    manifest_path.write_text(manifest_path.read_text() + " ")
    result = _discover(scenario_root, scenario, now)
    passed = (
        result.status == SupervisedProviderDiscoveryStatus.BLOCKED
        and "linked input hash mismatch" in str(result.blocked_reason)
        and not _manifest_paths(scenario_root)
        and not _loop_record_paths(scenario_root)
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        passed=passed,
        reason="discovery blocked a request with changed linked evidence",
    )


def _stop_on_block_handoff(
    root: Path,
    prerequisite_path: Path,
    now: datetime,
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    scenario = (
        SupervisedProviderDiscoveryRehearsalScenario.STOP_ON_BLOCK_HANDOFF
    )
    scenario_root = root / scenario.value
    _requests(
        scenario_root,
        scenario,
        prerequisite_path,
        ("successful_assembly", "stale_target_rejected", "restart_reuse"),
        now,
    )
    result = _discover(scenario_root, scenario, now, maximum_requests=3)
    record = run_finite_supervised_provider_loop(
        manifest_path=_completed_manifest_path(result),
        clock=lambda: now,
    )
    passed = (
        result.status == SupervisedProviderDiscoveryStatus.COMPLETED
        and record.status == FiniteSupervisedProviderStatus.BLOCKED
        and len(record.completed_request_ids) == 1
        and record.blocked_request_id
        == "stale_target_rejected-stop_on_block_handoff"
        and not (
            scenario_root
            / "request-outputs"
            / "successful_assembly"
            / "operator-runs"
        ).exists()
    )
    return _result(
        scenario_root,
        scenario,
        discovery_result_paths=_discovery_result_paths(scenario_root),
        finite_manifest_paths=_manifest_paths(scenario_root),
        loop_record_paths=_loop_record_paths(scenario_root),
        passed=passed,
        reason="discovered finite loop stopped before later blocked work",
    )


def _discover(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryRehearsalScenario,
    now: datetime,
    *,
    maximum_requests: int = 2,
    make_requests: bool = True,
) -> SupervisedProviderDiscoveryResult:
    if make_requests:
        (scenario_root / "reviewed").mkdir(parents=True, exist_ok=True)
    policy = SupervisedProviderDiscoveryPolicy(
        discovery_id=f"{scenario.value}-discovery",
        discovery_policy_version="supervised_provider_discovery_v1",
        request_directory=str(scenario_root / "reviewed"),
        maximum_requests=maximum_requests,
        finite_loop_id=f"{scenario.value}-loop",
        finite_output_root=str(scenario_root / "loop-output"),
        created_at=now,
        evidence_refs=("discovery-handoff-rehearsal:no-network",),
    )
    return discover_supervised_provider_requests(
        policy=policy,
        output_root=scenario_root / "discovery-output",
        clock=lambda: now,
    )


def _requests(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryRehearsalScenario,
    prerequisite_path: Path,
    prerequisite_scenarios: tuple[str, ...],
    now: datetime,
) -> tuple[SupervisedProviderOperatorRequest, ...]:
    requests = tuple(
        _request(
            scenario_root,
            scenario,
            prerequisite_path,
            prerequisite_scenario,
            now,
        )
        for prerequisite_scenario in prerequisite_scenarios
    )
    for request in requests:
        write_supervised_provider_operator_request(
            request, scenario_root / "reviewed"
        )
    return requests


def _request(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryRehearsalScenario,
    prerequisite_path: Path,
    prerequisite_scenario: str,
    now: datetime,
) -> SupervisedProviderOperatorRequest:
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
    return SupervisedProviderOperatorRequest(
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
        evidence_refs=("discovery-handoff-rehearsal:no-network",),
    )


def _result(
    scenario_root: Path,
    scenario: SupervisedProviderDiscoveryRehearsalScenario,
    *,
    discovery_result_paths: tuple[Path, ...],
    passed: bool,
    reason: str,
    finite_manifest_paths: tuple[Path, ...] = (),
    loop_record_paths: tuple[Path, ...] = (),
) -> SupervisedProviderDiscoveryRehearsalScenarioResult:
    excluded = {
        *discovery_result_paths,
        *finite_manifest_paths,
        *loop_record_paths,
    }
    evidence_paths = tuple(
        path
        for path in sorted(scenario_root.rglob("*.json"))
        if path not in excluded
    )
    return SupervisedProviderDiscoveryRehearsalScenarioResult(
        scenario=scenario,
        passed=passed,
        discovery_result_paths=tuple(
            str(path) for path in discovery_result_paths
        ),
        discovery_result_sha256s=tuple(
            _file_sha256(path) for path in discovery_result_paths
        ),
        finite_manifest_paths=tuple(
            str(path) for path in finite_manifest_paths
        ),
        finite_manifest_sha256s=tuple(
            _file_sha256(path) for path in finite_manifest_paths
        ),
        loop_record_paths=tuple(str(path) for path in loop_record_paths),
        loop_record_sha256s=tuple(
            _file_sha256(path) for path in loop_record_paths
        ),
        evidence_paths=tuple(str(path) for path in evidence_paths),
        evidence_sha256s=tuple(_file_sha256(path) for path in evidence_paths),
        reason=reason,
    )


def _verify_report_evidence(
    report: SupervisedProviderDiscoveryRehearsalReport,
) -> None:
    root = Path(report.evidence_root)
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
        raise ValueError("discovery rehearsal prerequisite did not pass")
    if _prohibited_artifact_paths(root) != report.prohibited_artifact_paths:
        raise ValueError("discovery rehearsal prohibited evidence changed")
    for scenario in report.scenarios:
        for path_value, digest in zip(
            scenario.discovery_result_paths,
            scenario.discovery_result_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            result = load_supervised_provider_discovery_result(path)
            verify_supervised_provider_discovery_result(result)
            _verify_discovery_outcome(scenario.scenario, result)
        for path_value, digest in zip(
            scenario.finite_manifest_paths,
            scenario.finite_manifest_sha256s,
            strict=True,
        ):
            path = Path(path_value)
            _require_hash(path, digest)
            load_finite_supervised_provider_manifest(path)
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


def _verify_discovery_outcome(
    scenario: SupervisedProviderDiscoveryRehearsalScenario,
    result,
) -> None:
    blocked = {
        SupervisedProviderDiscoveryRehearsalScenario.EMPTY_DIRECTORY_BLOCK,
        SupervisedProviderDiscoveryRehearsalScenario.OVER_LIMIT_BLOCK,
        SupervisedProviderDiscoveryRehearsalScenario.CHANGED_INPUT_BLOCK,
    }
    if (
        scenario in blocked
        and result.status != SupervisedProviderDiscoveryStatus.BLOCKED
    ):
        raise ValueError("discovery rehearsal blocked outcome changed")
    if (
        scenario not in blocked
        and result.status != SupervisedProviderDiscoveryStatus.COMPLETED
    ):
        raise ValueError("discovery rehearsal completed outcome changed")


def _discovery_result_paths(scenario_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (scenario_root / "discovery-output" / "discoveries").glob(
                "*.json"
            )
        )
    )


def _manifest_paths(scenario_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted(
            (scenario_root / "discovery-output" / "finite-manifests").glob(
                "*.json"
            )
        )
    )


def _loop_record_paths(scenario_root: Path) -> tuple[Path, ...]:
    return tuple(
        sorted((scenario_root / "loop-output" / "loops").glob("*.json"))
    )


def _completed_manifest_path(
    result: SupervisedProviderDiscoveryResult,
) -> Path:
    if (
        result.status != SupervisedProviderDiscoveryStatus.COMPLETED
        or result.finite_manifest_path is None
    ):
        raise ValueError("discovery rehearsal expected completed manifest")
    return Path(result.finite_manifest_path)


def _prohibited_artifact_paths(root: Path) -> tuple[str, ...]:
    return tuple(
        str(path)
        for path in sorted(root.rglob("*"))
        if path.is_dir() and path.name in _PROHIBITED_DIRECTORY_NAMES
    )


def _require_hash(path: Path, expected: str) -> None:
    if not path.is_file() or _file_sha256(path) != expected:
        raise ValueError(f"discovery rehearsal evidence changed: {path}")


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
        raise ValueError("discovery rehearsal ID must be a safe path component")
