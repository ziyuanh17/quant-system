"""Test research-batch simulation runner behavior."""

from datetime import UTC, date, datetime, timedelta
from pathlib import Path

from quant.models.research import (
    ResearchEnvironmentSnapshot,
    ResearchTrialStatus,
)
from quant.research import (
    load_research_trials,
    run_aapl_research_batch_v1_evaluations,
    verify_evaluation_artifacts,
    write_aapl_strategy_research_batch_v1_artifacts,
)

SHA256 = "a" * 64


def test_run_aapl_research_batch_v1_evaluations_records_all_trials(
    tmp_path,
) -> None:
    environment = _environment()
    batch_paths = write_aapl_strategy_research_batch_v1_artifacts(
        market_bars_path=_write_market_bars(tmp_path),
        feature_path=_write_features(tmp_path),
        environment=environment,
        output_root=tmp_path / "batches",
        created_at=datetime(2026, 6, 24, tzinfo=UTC),
        min_rows=20,
    )

    evaluation_dirs = run_aapl_research_batch_v1_evaluations(
        batch_dir=Path(batch_paths.output_dir),
        output_root=tmp_path / "evaluations",
        environment=environment,
        started_at=datetime(2026, 6, 24, 1, tzinfo=UTC),
    )

    assert len(evaluation_dirs) == 5
    statuses = {}
    for evaluation_dir in evaluation_dirs:
        verify_evaluation_artifacts(evaluation_dir)
        trials = load_research_trials(evaluation_dir / "trials.jsonl")
        assert len(trials) == 1
        statuses[trials[0].candidate_id] = trials[0].status

    assert statuses == {
        "aapl-momentum-baseline-5-20-v1": ResearchTrialStatus.SUCCEEDED,
        "aapl-feature-momentum-baseline-5-20-v1": (
            ResearchTrialStatus.SUCCEEDED
        ),
        "aapl-target-native-trend-5-20-v1": ResearchTrialStatus.ABANDONED,
        "aapl-vol-adjusted-trend-5-20-20-v1": (
            ResearchTrialStatus.ABANDONED
        ),
        "aapl-mean-reversion-counterweight-5-20-v1": (
            ResearchTrialStatus.ABANDONED
        ),
    }


def test_run_aapl_research_batch_v1_writes_backtest_artifacts(tmp_path) -> None:
    environment = _environment()
    batch_paths = write_aapl_strategy_research_batch_v1_artifacts(
        market_bars_path=_write_market_bars(tmp_path),
        feature_path=_write_features(tmp_path),
        environment=environment,
        output_root=tmp_path / "batches",
        created_at=datetime(2026, 6, 24, tzinfo=UTC),
        min_rows=20,
    )

    evaluation_dirs = run_aapl_research_batch_v1_evaluations(
        batch_dir=Path(batch_paths.output_dir),
        output_root=tmp_path / "evaluations",
        environment=environment,
        started_at=datetime(2026, 6, 24, 1, tzinfo=UTC),
    )

    completed_dirs = [
        evaluation_dir
        for evaluation_dir in evaluation_dirs
        if (evaluation_dir / "backtest" / "summary.json").is_file()
    ]

    assert len(completed_dirs) == 2
    for evaluation_dir in completed_dirs:
        assert (evaluation_dir / "backtest" / "trades.csv").is_file()
        trials = load_research_trials(evaluation_dir / "trials.jsonl")
        assert len(trials[0].artifact_paths) == 2


def _environment() -> ResearchEnvironmentSnapshot:
    return ResearchEnvironmentSnapshot(
        source_commit="abc123",
        dependency_lock_sha256=SHA256,
        python_version="3.12.13",
        platform="linux-x86_64",
        evaluator_version="research-batch-runner-v1",
    )


def _write_market_bars(tmp_path) -> Path:
    path = tmp_path / "AAPL.csv"
    rows = ["date,symbol,open,high,low,close,volume"]
    for offset in range(40):
        day = date(2024, 1, 1) + timedelta(days=offset)
        close = 100 + offset + (offset % 5)
        rows.append(
            f"{day.isoformat()},AAPL,{close - 1},{close + 1},"
            f"{close - 2},{close},1000"
        )
    path.write_text("\n".join(rows) + "\n")
    return path


def _write_features(tmp_path) -> Path:
    path = tmp_path / "AAPL-features.csv"
    rows = ["date,symbol,close,ma_5,ma_20"]
    for offset in range(40):
        day = date(2024, 1, 1) + timedelta(days=offset)
        close = 100 + offset + (offset % 5)
        ma_5 = "" if offset < 4 else str(close - 2)
        ma_20 = "" if offset < 19 else str(close - 10)
        rows.append(f"{day.isoformat()},AAPL,{close},{ma_5},{ma_20}")
    path.write_text("\n".join(rows) + "\n")
    return path
