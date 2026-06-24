"""Test reviewed research-only batch builders."""

from datetime import UTC, datetime

import pytest

from quant.models.research import (
    ResearchEnvironmentSnapshot,
    ResearchInputKind,
    ResearchInputSnapshot,
)
from quant.research import (
    AAPL_RESEARCH_BATCH_V1,
    build_aapl_strategy_research_batch_v1,
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
