"""Build reviewed research-only strategy batch specifications."""

import hashlib
from datetime import date, datetime
from pathlib import Path

from quant.data.validation import validate_market_bars_csv
from quant.features.loader import load_feature_csv
from quant.models.research import (
    EvaluationSplitPolicy,
    ResearchBatchArtifactPaths,
    ResearchBatchSpec,
    ResearchEnvironmentSnapshot,
    ResearchInputKind,
    ResearchInputSnapshot,
    ResearchParameter,
    SimulationScenario,
    StrategyCandidateSpec,
)
from quant.research.artifacts import write_research_batch_spec

AAPL_RESEARCH_BATCH_V1 = "aapl-strategy-research-batch-v1"
AAPL_RESEARCH_BATCH_V2 = "aapl-strategy-research-batch-v2"
AAPL_RESEARCH_BATCH_SCHEMA_VERSION = "aapl_research_inputs_v1"


def write_aapl_strategy_research_batch_v1_artifacts(
    *,
    market_bars_path: Path,
    feature_path: Path,
    environment: ResearchEnvironmentSnapshot,
    output_root: Path,
    created_at: datetime,
    min_rows: int = 1,
) -> ResearchBatchArtifactPaths:
    """Validate AAPL inputs and persist the first research-only batch."""
    market_bars_input = build_validated_market_bars_input_snapshot(
        market_bars_path, symbol="AAPL", min_rows=min_rows
    )
    feature_input = build_feature_input_snapshot(feature_path, symbol="AAPL")
    batch = build_aapl_strategy_research_batch_v1(
        market_bars_input=market_bars_input,
        feature_input=feature_input,
        environment=environment,
        created_at=created_at,
    )
    return write_research_batch_spec(batch, output_root)


def write_aapl_strategy_research_batch_v2_artifacts(
    *,
    market_bars_path: Path,
    feature_path: Path,
    environment: ResearchEnvironmentSnapshot,
    output_root: Path,
    created_at: datetime,
    min_rows: int = 1,
) -> ResearchBatchArtifactPaths:
    """Validate AAPL inputs and persist the second research-only batch."""
    market_bars_input = build_validated_market_bars_input_snapshot(
        market_bars_path, symbol="AAPL", min_rows=min_rows
    )
    feature_input = build_feature_input_snapshot(feature_path, symbol="AAPL")
    batch = build_aapl_strategy_research_batch_v2(
        market_bars_input=market_bars_input,
        feature_input=feature_input,
        environment=environment,
        created_at=created_at,
    )
    return write_research_batch_spec(batch, output_root)


def build_validated_market_bars_input_snapshot(
    path: Path,
    *,
    symbol: str,
    min_rows: int = 1,
) -> ResearchInputSnapshot:
    """Return an input snapshot after market-bar validation passes."""
    report = validate_market_bars_csv(path, symbol, min_rows=min_rows)
    if not report.passed:
        raise ValueError(f"market bars validation failed for {symbol}: {path}")
    digest = _file_sha256(path)
    return ResearchInputSnapshot(
        input_id=f"{symbol.lower()}-market-bars-{digest[:12]}",
        kind=ResearchInputKind.MARKET_BARS,
        path=str(path),
        sha256=digest,
        schema_version=AAPL_RESEARCH_BATCH_SCHEMA_VERSION,
        event_time_column="date",
    )


def build_feature_input_snapshot(
    path: Path,
    *,
    symbol: str,
) -> ResearchInputSnapshot:
    """Return an input snapshot after feature artifact validation passes."""
    features = load_feature_csv(path, symbol)
    missing = [
        column
        for column in ("ma_5", "ma_20")
        if column not in features.frame.columns
    ]
    if missing:
        raise ValueError(f"feature artifact is missing columns: {missing}")
    digest = _file_sha256(path)
    return ResearchInputSnapshot(
        input_id=f"{symbol.lower()}-features-{digest[:12]}",
        kind=ResearchInputKind.FEATURES,
        path=str(path),
        sha256=digest,
        schema_version=AAPL_RESEARCH_BATCH_SCHEMA_VERSION,
        event_time_column="date",
    )


def build_aapl_strategy_research_batch_v1(
    *,
    market_bars_input: ResearchInputSnapshot,
    feature_input: ResearchInputSnapshot,
    environment: ResearchEnvironmentSnapshot,
    created_at: datetime,
) -> ResearchBatchSpec:
    """Return the first reviewed AAPL strategy research batch."""
    _require_input_kind(
        market_bars_input, ResearchInputKind.MARKET_BARS, "market_bars_input"
    )
    _require_input_kind(
        feature_input, ResearchInputKind.FEATURES, "feature_input"
    )

    return ResearchBatchSpec(
        batch_id=AAPL_RESEARCH_BATCH_V1,
        objective=(
            "Evaluate a small AAPL research-only batch before any paper, "
            "Alpaca, scheduler, runtime, broker, order, or fill promotion."
        ),
        symbols=("AAPL",),
        candidates=(
            _momentum_baseline(environment, market_bars_input),
            _feature_momentum_baseline(environment, feature_input),
            _target_native_trend(environment, market_bars_input),
            _volatility_adjusted_trend(environment, market_bars_input),
            _mean_reversion_counterweight(environment, market_bars_input),
        ),
        evidence_required=(
            "candidate ID and family ID",
            "hypothesis",
            "strategy implementation version",
            "parameter values",
            "input data paths and hashes",
            "feature artifact paths and hashes when used",
            "split policy",
            "fees, slippage, and initial cash",
            "source commit",
            "dependency lock hash",
            "backtest metrics",
            "target history or signal history",
            "trade list",
            "comparison against buy-and-hold and existing momentum",
            "pass/fail decision under a declared evaluation policy",
            "trial ledger entry for every attempted variant",
        ),
        stop_conditions=(
            "input data validation fails",
            "feature lineage is missing",
            "a candidate cannot identify source or data hashes",
            "split periods change after inspection",
            "the trial ledger omits attempted variants",
            "work drifts toward runtime, paper, Alpaca, broker, scheduler, "
            "order, or fill paths",
        ),
        created_at=created_at,
    )


def build_aapl_strategy_research_batch_v2(
    *,
    market_bars_input: ResearchInputSnapshot,
    feature_input: ResearchInputSnapshot,
    environment: ResearchEnvironmentSnapshot,
    created_at: datetime,
) -> ResearchBatchSpec:
    """Return the second reviewed AAPL batch with declared-notional sizing."""
    batch_v1 = build_aapl_strategy_research_batch_v1(
        market_bars_input=market_bars_input,
        feature_input=feature_input,
        environment=environment,
        created_at=created_at,
    )
    return batch_v1.model_copy(
        update={
            "batch_id": AAPL_RESEARCH_BATCH_V2,
            "objective": (
                "Evaluate AAPL target-native declared-policy sizing with a "
                "declared-notional trend candidate before any paper, Alpaca, "
                "scheduler, runtime, broker, order, or fill promotion."
            ),
            "candidates": (
                *batch_v1.candidates,
                _declared_notional_trend(environment, market_bars_input),
            ),
        }
    )


def _momentum_baseline(
    environment: ResearchEnvironmentSnapshot,
    market_bars_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-momentum-baseline-5-20-v1",
        research_family_id="momentum-baseline",
        hypothesis_id="trend-following-moving-average-cross-v1",
        hypothesis="A 5/20 moving-average crossover captures AAPL trends.",
        strategy_name="momentum",
        strategy_version="legacy_signal_v1",
        parameters=(
            ResearchParameter(name="fast_window", value=5),
            ResearchParameter(name="slow_window", value=20),
            ResearchParameter(name="sizing_policy", value="legacy_signal"),
        ),
        inputs=(market_bars_input,),
        environment=environment,
    )


def _feature_momentum_baseline(
    environment: ResearchEnvironmentSnapshot,
    feature_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-feature-momentum-baseline-5-20-v1",
        research_family_id="feature-momentum-baseline",
        hypothesis_id="feature-moving-average-cross-v1",
        hypothesis=(
            "A feature-backed 5/20 moving-average crossover reproduces the "
            "price momentum control while improving lineage."
        ),
        strategy_name="feature-momentum",
        strategy_version="legacy_feature_signal_v1",
        parameters=(
            ResearchParameter(name="fast_column", value="ma_5"),
            ResearchParameter(name="slow_column", value="ma_20"),
            ResearchParameter(name="sizing_policy", value="legacy_signal"),
        ),
        inputs=(feature_input,),
        environment=environment,
    )


def _target_native_trend(
    environment: ResearchEnvironmentSnapshot,
    market_bars_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-target-native-trend-5-20-v1",
        research_family_id="target-native-trend",
        hypothesis_id="signed-target-trend-following-v1",
        hypothesis=(
            "Expressing trend following as signed target shares makes long, "
            "flat, short, cover, and reversal semantics explicit."
        ),
        strategy_name="target-native-trend",
        strategy_version="research_target_v1",
        parameters=(
            ResearchParameter(name="fast_window", value=5),
            ResearchParameter(name="slow_window", value=20),
            ResearchParameter(name="long_target_shares", value=1),
            ResearchParameter(name="short_target_shares", value=-1),
            ResearchParameter(name="sizing_policy", value="fixed_shares_v1"),
        ),
        inputs=(market_bars_input,),
        environment=environment,
    )


def _volatility_adjusted_trend(
    environment: ResearchEnvironmentSnapshot,
    market_bars_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-vol-adjusted-trend-5-20-20-v1",
        research_family_id="volatility-adjusted-trend",
        hypothesis_id="volatility-scaled-target-trend-v1",
        hypothesis=(
            "Scaling target exposure down during higher recent volatility "
            "can reduce drawdown without destroying trend capture."
        ),
        strategy_name="volatility-adjusted-target-trend",
        strategy_version="research_target_v1",
        parameters=(
            ResearchParameter(name="fast_window", value=5),
            ResearchParameter(name="slow_window", value=20),
            ResearchParameter(name="volatility_window", value=20),
            ResearchParameter(name="base_target_shares", value=1.0),
            ResearchParameter(name="min_target_shares", value=0.25),
            ResearchParameter(name="max_target_shares", value=1.0),
            ResearchParameter(
                name="sizing_policy", value="fractional_research"
            ),
        ),
        inputs=(market_bars_input,),
        environment=environment,
    )


def _declared_notional_trend(
    environment: ResearchEnvironmentSnapshot,
    market_bars_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-declared-notional-trend-5-20-100k-v1",
        research_family_id="declared-notional-trend",
        hypothesis_id="declared-notional-target-trend-v1",
        hypothesis=(
            "A trend strategy can own its sizing decision by declaring target "
            "notional exposure and resolving that exposure to signed shares."
        ),
        strategy_name="declared-notional-trend",
        strategy_version="research_target_v1",
        parameters=(
            ResearchParameter(name="fast_window", value=5),
            ResearchParameter(name="slow_window", value=20),
            ResearchParameter(name="long_target_notional", value=100_000),
            ResearchParameter(name="short_target_notional", value=-100_000),
            ResearchParameter(
                name="sizing_policy", value="declared_notional_v1"
            ),
        ),
        inputs=(market_bars_input,),
        environment=environment,
    )


def _mean_reversion_counterweight(
    environment: ResearchEnvironmentSnapshot,
    market_bars_input: ResearchInputSnapshot,
) -> StrategyCandidateSpec:
    return _candidate(
        candidate_id="aapl-mean-reversion-counterweight-5-20-v1",
        research_family_id="mean-reversion-counterweight",
        hypothesis_id="moving-average-distance-reversion-v1",
        hypothesis=(
            "A simple mean-reversion target can counterbalance trend signals "
            "when price stretches far from its recent average."
        ),
        strategy_name="mean-reversion-counterweight",
        strategy_version="research_target_v1",
        parameters=(
            ResearchParameter(name="lookback_window", value=20),
            ResearchParameter(name="entry_zscore", value=1.5),
            ResearchParameter(name="exit_zscore", value=0.25),
            ResearchParameter(name="target_shares", value=1),
            ResearchParameter(name="sizing_policy", value="fixed_shares_v1"),
        ),
        inputs=(market_bars_input,),
        environment=environment,
    )


def _candidate(
    *,
    candidate_id: str,
    research_family_id: str,
    hypothesis_id: str,
    hypothesis: str,
    strategy_name: str,
    strategy_version: str,
    parameters: tuple[ResearchParameter, ...],
    inputs: tuple[ResearchInputSnapshot, ...],
    environment: ResearchEnvironmentSnapshot,
) -> StrategyCandidateSpec:
    return StrategyCandidateSpec(
        candidate_id=candidate_id,
        research_family_id=research_family_id,
        hypothesis_id=hypothesis_id,
        hypothesis=hypothesis,
        strategy_name=strategy_name,
        strategy_version=strategy_version,
        parameters=parameters,
        symbols=("AAPL",),
        inputs=inputs,
        split_policy=_split_policy(),
        simulation_scenarios=(
            SimulationScenario(
                name="base",
                initial_cash=100_000,
                fees=0.001,
                slippage_bps=5,
            ),
        ),
        benchmark_name="buy-and-hold",
        promotion_criteria_version="research_only_v1",
        source_commit=environment.source_commit,
        dependency_lock_sha256=environment.dependency_lock_sha256,
        random_seed=7,
    )


def _split_policy() -> EvaluationSplitPolicy:
    return EvaluationSplitPolicy(
        development_start=date(2020, 1, 1),
        development_end=date(2021, 12, 31),
        validation_start=date(2022, 1, 1),
        validation_end=date(2022, 12, 31),
        holdout_start=date(2023, 1, 1),
        holdout_end=date(2023, 12, 31),
    )


def _require_input_kind(
    input_snapshot: ResearchInputSnapshot,
    expected: ResearchInputKind,
    label: str,
) -> None:
    if input_snapshot.kind != expected:
        raise ValueError(f"{label} must have kind={expected.value}")


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
