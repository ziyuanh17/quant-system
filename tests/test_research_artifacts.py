import json
from datetime import UTC, date, datetime, timedelta

import pytest

from quant.models.research import (
    EvaluationSplitPolicy,
    ResearchEnvironmentSnapshot,
    ResearchInputKind,
    ResearchInputSnapshot,
    ResearchParameter,
    ResearchTrialRecord,
    ResearchTrialStatus,
    SimulationScenario,
    StrategyCandidateSpec,
)
from quant.research import (
    append_research_trial,
    build_evaluation_id,
    create_evaluation_artifacts,
    load_research_trials,
    verify_evaluation_artifacts,
)

SHA256 = "a" * 64


def test_create_evaluation_artifacts_writes_verifiable_manifests(
    tmp_path,
) -> None:
    candidate = _candidate()
    environment = _environment()

    paths = create_evaluation_artifacts(candidate, environment, tmp_path)
    evaluation_dir = tmp_path / candidate.candidate_id / paths.evaluation_id
    candidate_payload = json.loads(
        (evaluation_dir / "candidate.json").read_text()
    )

    assert paths.evaluation_id == build_evaluation_id(candidate, environment)
    assert paths.output_dir.endswith(paths.evaluation_id)
    assert candidate_payload["candidate_id"] == candidate.candidate_id
    verify_evaluation_artifacts(evaluation_dir)


def test_create_evaluation_artifacts_rejects_identity_collision(
    tmp_path,
) -> None:
    candidate = _candidate()
    environment = _environment()
    create_evaluation_artifacts(candidate, environment, tmp_path)

    with pytest.raises(FileExistsError):
        create_evaluation_artifacts(candidate, environment, tmp_path)


def test_verify_evaluation_artifacts_detects_tampering(tmp_path) -> None:
    candidate = _candidate()
    paths = create_evaluation_artifacts(candidate, _environment(), tmp_path)
    inputs_path = (
        tmp_path
        / candidate.candidate_id
        / paths.evaluation_id
        / "inputs.json"
    )
    inputs_path.write_text("[]\n")

    with pytest.raises(ValueError, match="immutable research artifact changed"):
        verify_evaluation_artifacts(
            tmp_path / candidate.candidate_id / paths.evaluation_id
        )


def test_trial_ledger_is_append_only_and_rejects_duplicates(tmp_path) -> None:
    candidate = _candidate()
    paths = create_evaluation_artifacts(candidate, _environment(), tmp_path)
    evaluation_dir = tmp_path / candidate.candidate_id / paths.evaluation_id
    first = _trial("trial-1", ResearchTrialStatus.SUCCEEDED)
    second = _trial("trial-2", ResearchTrialStatus.FAILED)

    append_research_trial(first, evaluation_dir)
    first_line = (evaluation_dir / "trials.jsonl").read_text().splitlines()[0]
    append_research_trial(second, evaluation_dir)

    loaded = load_research_trials(evaluation_dir / "trials.jsonl")
    assert loaded == (first, second)
    lines = (evaluation_dir / "trials.jsonl").read_text().splitlines()
    assert lines[0] == first_line
    with pytest.raises(ValueError, match="trial_id already exists"):
        append_research_trial(first, evaluation_dir)


def test_trial_ledger_rejects_candidate_mismatch(tmp_path) -> None:
    candidate = _candidate()
    paths = create_evaluation_artifacts(candidate, _environment(), tmp_path)
    evaluation_dir = tmp_path / candidate.candidate_id / paths.evaluation_id
    mismatched = _trial(
        "trial-other",
        ResearchTrialStatus.ABANDONED,
        candidate_id="other-candidate",
    )

    with pytest.raises(ValueError, match="candidate_id does not match"):
        append_research_trial(mismatched, evaluation_dir)


def test_create_evaluation_artifacts_rejects_unsafe_candidate_path(
    tmp_path,
) -> None:
    candidate = _candidate(candidate_id="../outside")

    with pytest.raises(ValueError, match="safe path segment"):
        create_evaluation_artifacts(candidate, _environment(), tmp_path)


def test_create_evaluation_artifacts_requires_matching_environment(
    tmp_path,
) -> None:
    candidate = _candidate()
    environment = ResearchEnvironmentSnapshot(
        source_commit="different",
        dependency_lock_sha256=SHA256,
        python_version="3.12.13",
        platform="linux-x86_64",
        evaluator_version="1",
    )

    with pytest.raises(ValueError, match="source commits differ"):
        create_evaluation_artifacts(candidate, environment, tmp_path)


def _candidate(*, candidate_id: str = "momentum-5-20") -> StrategyCandidateSpec:
    return StrategyCandidateSpec(
        candidate_id=candidate_id,
        research_family_id="momentum-family",
        hypothesis_id="trend-following-1",
        hypothesis="Moving-average crossovers capture persistent trends.",
        strategy_name="momentum",
        strategy_version="1",
        parameters=(
            ResearchParameter(name="fast_window", value=5),
            ResearchParameter(name="slow_window", value=20),
        ),
        symbols=("AAPL",),
        inputs=(
            ResearchInputSnapshot(
                input_id="aapl-bars-v1",
                kind=ResearchInputKind.MARKET_BARS,
                path="data/normalized/market_bars/AAPL.csv",
                sha256=SHA256,
                schema_version="1",
                event_time_column="date",
            ),
        ),
        split_policy=EvaluationSplitPolicy(
            development_start=date(2020, 1, 1),
            development_end=date(2021, 12, 31),
            validation_start=date(2022, 1, 1),
            validation_end=date(2022, 12, 31),
            holdout_start=date(2023, 1, 1),
            holdout_end=date(2023, 12, 31),
        ),
        simulation_scenarios=(
            SimulationScenario(name="base", fees=0.001, slippage_bps=5),
        ),
        benchmark_name="buy-and-hold",
        promotion_criteria_version="1",
        source_commit="abc123",
        dependency_lock_sha256=SHA256,
        random_seed=7,
    )


def _environment() -> ResearchEnvironmentSnapshot:
    return ResearchEnvironmentSnapshot(
        source_commit="abc123",
        dependency_lock_sha256=SHA256,
        python_version="3.12.13",
        platform="linux-x86_64",
        evaluator_version="1",
    )


def _trial(
    trial_id: str,
    status: ResearchTrialStatus,
    *,
    candidate_id: str = "momentum-5-20",
) -> ResearchTrialRecord:
    started_at = datetime(2026, 6, 11, tzinfo=UTC)
    return ResearchTrialRecord(
        trial_id=trial_id,
        research_family_id="momentum-family",
        candidate_id=candidate_id,
        status=status,
        started_at=started_at,
        completed_at=started_at + timedelta(seconds=1),
        message=f"{status.value} trial",
    )
