"""Test reviewed research-only batch builders."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from quant.models.research import (
    ResearchEnvironmentSnapshot,
    ResearchInputKind,
    ResearchInputSnapshot,
)
from quant.research import (
    AAPL_RESEARCH_BATCH_SCHEMA_VERSION,
    AAPL_RESEARCH_BATCH_V1,
    AAPL_RESEARCH_BATCH_V2,
    build_aapl_strategy_research_batch_v1,
    build_aapl_strategy_research_batch_v2,
    build_feature_input_snapshot,
    build_validated_market_bars_input_snapshot,
    verify_research_batch_artifacts,
    write_aapl_strategy_research_batch_v1_artifacts,
)

SHA256 = "a" * 64


def test_build_aapl_strategy_research_batch_v1_defines_candidate_set() -> None:
    batch = build_aapl_strategy_research_batch_v1(
        market_bars_input=_market_bars_input(),
        feature_input=_feature_input(),
        environment=_environment(),
        created_at=datetime(2026, 6, 24, tzinfo=UTC),
    )

    assert batch.batch_id == AAPL_RESEARCH_BATCH_V1
    assert batch.symbols == ("AAPL",)
    assert batch.broker_access_authorized is False
    assert batch.runtime_mutation_authorized is False
    assert batch.scheduler_authorized is False
    assert batch.order_submission_authorized is False
    assert tuple(candidate.candidate_id for candidate in batch.candidates) == (
        "aapl-momentum-baseline-5-20-v1",
        "aapl-feature-momentum-baseline-5-20-v1",
        "aapl-target-native-trend-5-20-v1",
        "aapl-vol-adjusted-trend-5-20-20-v1",
        "aapl-mean-reversion-counterweight-5-20-v1",
    )
    assert tuple(
        candidate.research_family_id for candidate in batch.candidates
    ) == (
        "momentum-baseline",
        "feature-momentum-baseline",
        "target-native-trend",
        "volatility-adjusted-trend",
        "mean-reversion-counterweight",
    )
    assert all(
        candidate.source_commit == "abc123" for candidate in batch.candidates
    )
    assert all(
        candidate.dependency_lock_sha256 == SHA256
        for candidate in batch.candidates
    )
    assert any(
        parameter.name == "sizing_policy"
        and parameter.value == "fractional_research"
        for candidate in batch.candidates
        for parameter in candidate.parameters
    )


def test_build_aapl_strategy_research_batch_v2_adds_declared_notional() -> None:
    batch = build_aapl_strategy_research_batch_v2(
        market_bars_input=_market_bars_input(),
        feature_input=_feature_input(),
        environment=_environment(),
        created_at=datetime(2026, 6, 25, tzinfo=UTC),
    )

    assert batch.batch_id == AAPL_RESEARCH_BATCH_V2
    assert tuple(candidate.candidate_id for candidate in batch.candidates) == (
        "aapl-momentum-baseline-5-20-v1",
        "aapl-feature-momentum-baseline-5-20-v1",
        "aapl-target-native-trend-5-20-v1",
        "aapl-vol-adjusted-trend-5-20-20-v1",
        "aapl-mean-reversion-counterweight-5-20-v1",
        "aapl-declared-notional-trend-5-20-100k-v1",
    )
    declared_notional = batch.candidates[-1]
    assert declared_notional.research_family_id == "declared-notional-trend"
    assert any(
        parameter.name == "sizing_policy"
        and parameter.value == "declared_notional_v1"
        for parameter in declared_notional.parameters
    )
    assert batch.order_submission_authorized is False


def test_build_aapl_strategy_research_batch_v1_uses_expected_inputs() -> None:
    batch = build_aapl_strategy_research_batch_v1(
        market_bars_input=_market_bars_input(),
        feature_input=_feature_input(),
        environment=_environment(),
        created_at=datetime(2026, 6, 24, tzinfo=UTC),
    )

    inputs_by_candidate = {
        candidate.candidate_id: candidate.inputs
        for candidate in batch.candidates
    }

    assert (
        inputs_by_candidate["aapl-feature-momentum-baseline-5-20-v1"][0].kind
        == ResearchInputKind.FEATURES
    )
    for candidate_id, inputs in inputs_by_candidate.items():
        if candidate_id != "aapl-feature-momentum-baseline-5-20-v1":
            assert inputs[0].kind == ResearchInputKind.MARKET_BARS


def test_build_aapl_research_batch_v1_rejects_wrong_input_kind() -> None:
    with pytest.raises(ValueError, match="market_bars_input"):
        build_aapl_strategy_research_batch_v1(
            market_bars_input=_feature_input(),
            feature_input=_feature_input(),
            environment=_environment(),
            created_at=datetime(2026, 6, 24, tzinfo=UTC),
        )


def test_build_validated_market_bars_input_snapshot_hashes_valid_csv(
    tmp_path,
) -> None:
    path = _write_market_bars(tmp_path)

    snapshot = build_validated_market_bars_input_snapshot(path, symbol="AAPL")

    assert snapshot.kind == ResearchInputKind.MARKET_BARS
    assert snapshot.path == str(path)
    assert snapshot.sha256 != SHA256
    assert snapshot.input_id.startswith("aapl-market-bars-")
    assert snapshot.schema_version == AAPL_RESEARCH_BATCH_SCHEMA_VERSION


def test_build_validated_market_bars_input_snapshot_rejects_invalid_csv(
    tmp_path,
) -> None:
    path = _write_market_bars(tmp_path, symbol="MSFT")

    with pytest.raises(ValueError, match="market bars validation failed"):
        build_validated_market_bars_input_snapshot(path, symbol="AAPL")


def test_build_feature_input_snapshot_hashes_valid_csv(tmp_path) -> None:
    path = _write_features(tmp_path)

    snapshot = build_feature_input_snapshot(path, symbol="AAPL")

    assert snapshot.kind == ResearchInputKind.FEATURES
    assert snapshot.path == str(path)
    assert snapshot.sha256 != SHA256
    assert snapshot.input_id.startswith("aapl-features-")
    assert snapshot.schema_version == AAPL_RESEARCH_BATCH_SCHEMA_VERSION


def test_build_feature_input_snapshot_rejects_missing_batch_columns(
    tmp_path,
) -> None:
    path = _write_features(tmp_path, include_moving_averages=False)

    with pytest.raises(ValueError, match="missing columns"):
        build_feature_input_snapshot(path, symbol="AAPL")


def test_write_aapl_strategy_research_batch_v1_artifacts_materializes_batch(
    tmp_path,
) -> None:
    market_bars_path = _write_market_bars(tmp_path)
    feature_path = _write_features(tmp_path)

    paths = write_aapl_strategy_research_batch_v1_artifacts(
        market_bars_path=market_bars_path,
        feature_path=feature_path,
        environment=_environment(),
        output_root=tmp_path / "research-batches",
        created_at=datetime(2026, 6, 24, tzinfo=UTC),
    )

    batch_dir = Path(paths.output_dir)
    verify_research_batch_artifacts(batch_dir)
    payload = json.loads(Path(paths.batch_json).read_text())
    assert payload["batch_id"] == AAPL_RESEARCH_BATCH_V1
    assert payload["candidates"][0]["inputs"][0]["sha256"] != SHA256
    assert payload["order_submission_authorized"] is False


def _market_bars_input() -> ResearchInputSnapshot:
    return ResearchInputSnapshot(
        input_id="aapl-validated-market-bars-v1",
        kind=ResearchInputKind.MARKET_BARS,
        path="data/normalized/market_bars/AAPL.csv",
        sha256=SHA256,
        schema_version="1",
        event_time_column="date",
    )


def _feature_input() -> ResearchInputSnapshot:
    return ResearchInputSnapshot(
        input_id="aapl-technical-features-v1",
        kind=ResearchInputKind.FEATURES,
        path="data/features/AAPL/technical.csv",
        sha256=SHA256,
        schema_version="1",
        event_time_column="date",
    )


def _environment() -> ResearchEnvironmentSnapshot:
    return ResearchEnvironmentSnapshot(
        source_commit="abc123",
        dependency_lock_sha256=SHA256,
        python_version="3.12.13",
        platform="linux-x86_64",
        evaluator_version="research-batch-v1",
    )


def _write_market_bars(tmp_path, *, symbol: str = "AAPL") -> Path:
    path = tmp_path / "AAPL.csv"
    path.write_text(
        "date,symbol,open,high,low,close,volume\n"
        f"2024-01-01,{symbol},10,11,9,10,100\n"
        f"2024-01-02,{symbol},11,12,10,11,110\n"
        f"2024-01-03,{symbol},12,13,11,12,120\n"
    )
    return path


def _write_features(
    tmp_path,
    *,
    include_moving_averages: bool = True,
) -> Path:
    path = tmp_path / "AAPL-features.csv"
    if include_moving_averages:
        path.write_text(
            "date,symbol,close,ma_5,ma_20\n"
            "2024-01-01,AAPL,10,,\n"
            "2024-01-02,AAPL,11,10.5,\n"
            "2024-01-03,AAPL,12,11,11\n"
        )
    else:
        path.write_text(
            "date,symbol,close\n"
            "2024-01-01,AAPL,10\n"
            "2024-01-02,AAPL,11\n"
        )
    return path
