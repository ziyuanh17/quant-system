"""Persist immutable research evaluations and trial ledgers."""

import hashlib
import json
import os
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ValidationError

from quant.models.research import (
    ResearchArtifactDigest,
    ResearchEnvironmentSnapshot,
    ResearchEvaluationArtifactPaths,
    ResearchEvaluationManifest,
    ResearchTrialRecord,
    StrategyCandidateSpec,
)


def build_evaluation_id(
    candidate: StrategyCandidateSpec,
    environment: ResearchEnvironmentSnapshot,
) -> str:
    """Return a deterministic identity for candidate and environment content."""
    content = {
        "candidate": candidate.model_dump(mode="json"),
        "environment": environment.model_dump(mode="json"),
    }
    return hashlib.sha256(_canonical_json_bytes(content)).hexdigest()


def create_evaluation_artifacts(
    candidate: StrategyCandidateSpec,
    environment: ResearchEnvironmentSnapshot,
    output_root: Path,
) -> ResearchEvaluationArtifactPaths:
    """Create immutable evaluation manifests and an empty append-only ledger."""
    _require_safe_path_segment(candidate.candidate_id, "candidate_id")
    _require_matching_environment(candidate, environment)
    evaluation_id = build_evaluation_id(candidate, environment)
    output_dir = output_root / candidate.candidate_id / evaluation_id
    output_dir.mkdir(parents=True, exist_ok=False)

    contents = _immutable_contents(candidate, environment)
    digests = tuple(
        _write_immutable_json(output_dir / name, content)
        for name, content in contents.items()
    )
    manifest = ResearchEvaluationManifest(
        evaluation_id=evaluation_id,
        candidate_id=candidate.candidate_id,
        immutable_artifacts=digests,
    )
    manifest_path = output_dir / "manifest.json"
    _write_exclusive(manifest_path, _pretty_json_bytes(manifest))

    trials_path = output_dir / "trials.jsonl"
    trials_path.open("x").close()
    return ResearchEvaluationArtifactPaths(
        evaluation_id=evaluation_id,
        output_dir=str(output_dir),
        candidate_json=str(output_dir / "candidate.json"),
        environment_json=str(output_dir / "environment.json"),
        inputs_json=str(output_dir / "inputs.json"),
        splits_json=str(output_dir / "splits.json"),
        scenarios_json=str(output_dir / "scenarios.json"),
        manifest_json=str(manifest_path),
        trials_jsonl=str(trials_path),
    )


def append_research_trial(
    record: ResearchTrialRecord,
    evaluation_dir: Path,
) -> Path:
    """Append one unique, candidate-matched trial to an existing ledger."""
    verify_evaluation_artifacts(evaluation_dir)
    candidate = _load_candidate(evaluation_dir / "candidate.json")
    if record.candidate_id != candidate.candidate_id:
        raise ValueError("trial candidate_id does not match evaluation")
    if record.research_family_id != candidate.research_family_id:
        raise ValueError("trial research_family_id does not match evaluation")

    ledger_path = evaluation_dir / "trials.jsonl"
    existing = load_research_trials(ledger_path)
    if any(trial.trial_id == record.trial_id for trial in existing):
        raise ValueError(f"trial_id already exists: {record.trial_id}")

    line = _canonical_json_bytes(record.model_dump(mode="json")) + b"\n"
    descriptor = os.open(ledger_path, os.O_APPEND | os.O_WRONLY)
    try:
        os.write(descriptor, line)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    return ledger_path


def load_research_trials(ledger_path: Path) -> tuple[ResearchTrialRecord, ...]:
    """Load and validate every append-only trial ledger line."""
    trials: list[ResearchTrialRecord] = []
    for line_number, line in enumerate(ledger_path.read_text().splitlines(), 1):
        try:
            trials.append(ResearchTrialRecord.model_validate_json(line))
        except (ValidationError, ValueError) as exc:
            raise ValueError(
                f"invalid research trial ledger line {line_number}: {exc}"
            ) from exc
    return tuple(trials)


def verify_evaluation_artifacts(evaluation_dir: Path) -> None:
    """Fail when immutable evaluation identity or content has changed."""
    manifest_path = evaluation_dir / "manifest.json"
    manifest = ResearchEvaluationManifest.model_validate_json(
        manifest_path.read_text()
    )
    candidate = _load_candidate(evaluation_dir / "candidate.json")
    environment = ResearchEnvironmentSnapshot.model_validate_json(
        (evaluation_dir / "environment.json").read_text()
    )
    expected_id = build_evaluation_id(candidate, environment)
    _require_matching_environment(candidate, environment)
    if manifest.evaluation_id != expected_id:
        raise ValueError("evaluation identity does not match candidate content")
    if evaluation_dir.name != expected_id:
        raise ValueError("evaluation directory name does not match identity")

    expected_digests = tuple(
        ResearchArtifactDigest(
            relative_path=name,
            sha256=hashlib.sha256(_pretty_json_bytes(content)).hexdigest(),
        )
        for name, content in _immutable_contents(candidate, environment).items()
    )
    if manifest.immutable_artifacts != expected_digests:
        raise ValueError("evaluation manifest does not match expected content")

    for artifact in expected_digests:
        path = evaluation_dir / artifact.relative_path
        if not path.is_file():
            raise ValueError(f"immutable research artifact is missing: {path}")
        if _file_sha256(path) != artifact.sha256:
            raise ValueError(f"immutable research artifact changed: {path}")

    load_research_trials(evaluation_dir / "trials.jsonl")


def _write_immutable_json(path: Path, content: Any) -> ResearchArtifactDigest:
    payload = _pretty_json_bytes(content)
    _write_exclusive(path, payload)
    return ResearchArtifactDigest(
        relative_path=path.name,
        sha256=hashlib.sha256(payload).hexdigest(),
    )


def _write_exclusive(path: Path, payload: bytes) -> None:
    with path.open("xb") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())


def _pretty_json_bytes(content: Any) -> bytes:
    value = _json_value(content)
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def _canonical_json_bytes(content: Any) -> bytes:
    return json.dumps(content, separators=(",", ":"), sort_keys=True).encode()


def _load_candidate(path: Path) -> StrategyCandidateSpec:
    return StrategyCandidateSpec.model_validate_json(path.read_text())


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _immutable_contents(
    candidate: StrategyCandidateSpec,
    environment: ResearchEnvironmentSnapshot,
) -> dict[str, Any]:
    return {
        "candidate.json": candidate,
        "environment.json": environment,
        "inputs.json": candidate.inputs,
        "splits.json": candidate.split_policy,
        "scenarios.json": candidate.simulation_scenarios,
    }


def _json_value(content: Any) -> Any:
    if isinstance(content, BaseModel):
        return content.model_dump(mode="json")
    if isinstance(content, tuple | list):
        return [_json_value(item) for item in content]
    if isinstance(content, dict):
        return {key: _json_value(value) for key, value in content.items()}
    return content


def _require_matching_environment(
    candidate: StrategyCandidateSpec,
    environment: ResearchEnvironmentSnapshot,
) -> None:
    if candidate.source_commit != environment.source_commit:
        raise ValueError("candidate and environment source commits differ")
    if candidate.dependency_lock_sha256 != environment.dependency_lock_sha256:
        raise ValueError("candidate and environment dependency locks differ")


def _require_safe_path_segment(value: str, label: str) -> None:
    if value in {"", ".", ".."} or "/" in value or "\\" in value:
        raise ValueError(f"{label} must be a safe path segment")
