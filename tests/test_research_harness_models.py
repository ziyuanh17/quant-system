from datetime import UTC, date, datetime

import pandas as pd
import pytest
from pydantic import ValidationError

from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.research import (
    EvaluationSplitPolicy,
    PointInTimePolicy,
    ResearchInputKind,
    ResearchInputSnapshot,
    ResearchParameter,
    ResearchTrialRecord,
    ResearchTrialStatus,
    SimulationScenario,
    StrategyCandidateSpec,
)
from quant.research import (
    FeatureStrategySimulationAdapter,
    PriceStrategySimulationAdapter,
)
from quant.strategies import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
    MomentumConfig,
    MomentumStrategy,
)

SHA256 = "a" * 64


def test_candidate_spec_round_trips_with_reproducibility_identity() -> None:
    candidate = _candidate_spec()

    loaded = StrategyCandidateSpec.model_validate_json(
        candidate.model_dump_json()
    )

    assert loaded == candidate
    assert loaded.inputs[0].sha256 == SHA256
    assert loaded.simulation_scenarios[0].slippage_bps == 5


def test_candidate_spec_rejects_duplicate_parameter_names() -> None:
    with pytest.raises(ValidationError, match="parameter names must be unique"):
        _candidate_spec(
            parameters=(
                ResearchParameter(name="window", value=10),
                ResearchParameter(name="window", value=20),
            )
        )


def test_evaluation_split_policy_rejects_overlapping_periods() -> None:
    with pytest.raises(
        ValidationError,
        match="evaluation periods must be ordered and non-overlapping",
    ):
        EvaluationSplitPolicy(
            development_start=date(2020, 1, 1),
            development_end=date(2021, 12, 31),
            validation_start=date(2021, 12, 31),
            validation_end=date(2022, 12, 31),
            holdout_start=date(2023, 1, 1),
            holdout_end=date(2023, 12, 31),
        )


def test_point_in_time_policy_requires_availability_column() -> None:
    with pytest.raises(ValidationError, match="availability_time_column"):
        ResearchInputSnapshot(
            input_id="news-features-v1",
            kind=ResearchInputKind.FEATURES,
            path="data/features/news/AAPL.csv",
            sha256=SHA256,
            schema_version="1",
            event_time_column="published_at",
            point_in_time_policy=(
                PointInTimePolicy.EVENT_AND_AVAILABILITY_TIME
            ),
        )


def test_terminal_trial_requires_completion_time() -> None:
    with pytest.raises(
        ValidationError,
        match="terminal research trials require completed_at",
    ):
        ResearchTrialRecord(
            trial_id="trial-1",
            research_family_id="momentum-family",
            candidate_id="momentum-5-20",
            status=ResearchTrialStatus.FAILED,
            started_at=datetime(2026, 6, 11, tzinfo=UTC),
        )


def test_price_strategy_adapter_builds_aligned_simulation_input() -> None:
    prices = PriceData(symbol="AAPL", frame=_price_frame())
    strategy = MomentumStrategy(MomentumConfig(fast_window=2, slow_window=3))

    simulation_input = PriceStrategySimulationAdapter(strategy).build(prices)

    assert simulation_input.strategy_name == "momentum"
    assert simulation_input.symbol == "AAPL"
    assert simulation_input.close.index.equals(
        simulation_input.signals.entries.index
    )


def test_feature_strategy_adapter_builds_aligned_simulation_input() -> None:
    features = FeatureData(symbol="AAPL", frame=_feature_frame())
    strategy = FeatureMomentumStrategy(
        FeatureMomentumConfig(fast_column="ma_fast", slow_column="ma_slow")
    )

    simulation_input = FeatureStrategySimulationAdapter(strategy).build(
        features
    )

    assert simulation_input.strategy_name == "feature-momentum"
    assert simulation_input.symbol == "AAPL"
    assert simulation_input.close.index.equals(
        simulation_input.signals.entries.index
    )


def _candidate_spec(
    *,
    parameters: tuple[ResearchParameter, ...] = (
        ResearchParameter(name="fast_window", value=5),
        ResearchParameter(name="slow_window", value=20),
    ),
) -> StrategyCandidateSpec:
    return StrategyCandidateSpec(
        candidate_id="momentum-5-20",
        research_family_id="momentum-family",
        hypothesis_id="trend-following-1",
        hypothesis="Moving-average crossovers capture persistent trends.",
        strategy_name="momentum",
        strategy_version="1",
        parameters=parameters,
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


def _price_frame() -> pd.DataFrame:
    dates = [
        timestamp.date()
        for timestamp in pd.date_range("2024-01-01", periods=6)
    ]
    return pd.DataFrame(
        {
            "date": dates,
            "symbol": ["AAPL"] * 6,
            "open": [10.0, 11.0, 12.0, 11.0, 10.0, 12.0],
            "high": [11.0, 12.0, 13.0, 12.0, 11.0, 13.0],
            "low": [9.0, 10.0, 11.0, 10.0, 9.0, 11.0],
            "close": [10.0, 11.0, 12.0, 11.0, 10.0, 12.0],
            "volume": [100] * 6,
        }
    )


def _feature_frame() -> pd.DataFrame:
    prices = _price_frame()
    return prices[["date", "symbol", "close"]].assign(
        ma_fast=[None, 9.0, 12.0, 13.0, 9.0, 12.0],
        ma_slow=[None, 10.0, 10.0, 10.0, 10.0, 10.0],
    )
