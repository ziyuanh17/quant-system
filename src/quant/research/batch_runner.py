"""Run supported research candidates from reviewed batch artifacts."""

from datetime import datetime
from decimal import Decimal
from pathlib import Path

from quant.backtest import VectorBTBacktester, VectorBTTargetBacktester
from quant.backtest.artifacts import write_backtest_artifacts
from quant.data.csv_loader import load_price_csv
from quant.features.loader import load_feature_csv
from quant.models.backtest import BacktestConfig
from quant.models.research import (
    ResearchEnvironmentSnapshot,
    ResearchInputKind,
    ResearchTrialRecord,
    ResearchTrialStatus,
    StrategyCandidateSpec,
)
from quant.research.artifacts import (
    append_research_trial,
    build_evaluation_id,
    create_evaluation_artifacts,
    load_research_batch_spec,
    load_research_trials,
    verify_evaluation_artifacts,
    verify_research_batch_artifacts,
)
from quant.research.target_artifacts import write_target_frame
from quant.strategies import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
    MeanReversionCounterweightConfig,
    MeanReversionCounterweightStrategy,
    MomentumConfig,
    MomentumStrategy,
    TargetNativeTrendConfig,
    TargetNativeTrendStrategy,
    VolatilityAdjustedTrendConfig,
    VolatilityAdjustedTrendStrategy,
)

SUPPORTED_AAPL_RESEARCH_CANDIDATES = (
    "aapl-momentum-baseline-5-20-v1",
    "aapl-feature-momentum-baseline-5-20-v1",
    "aapl-target-native-trend-5-20-v1",
    "aapl-vol-adjusted-trend-5-20-20-v1",
    "aapl-mean-reversion-counterweight-5-20-v1",
)


def run_research_batch_evaluations(
    *,
    batch_dir: Path,
    output_root: Path,
    environment: ResearchEnvironmentSnapshot,
    started_at: datetime,
) -> tuple[Path, ...]:
    """Run supported candidates from any reviewed research batch."""
    return run_aapl_research_batch_v1_evaluations(
        batch_dir=batch_dir,
        output_root=output_root,
        environment=environment,
        started_at=started_at,
    )


def run_aapl_research_batch_v1_evaluations(
    *,
    batch_dir: Path,
    output_root: Path,
    environment: ResearchEnvironmentSnapshot,
    started_at: datetime,
) -> tuple[Path, ...]:
    """Run supported candidates and ledger unsupported candidates honestly."""
    verify_research_batch_artifacts(batch_dir)
    batch = load_research_batch_spec(batch_dir)
    evaluation_dirs: list[Path] = []

    for candidate in batch.candidates:
        evaluation_dir = _get_or_create_evaluation_dir(
            candidate=candidate,
            environment=environment,
            output_root=output_root,
        )
        evaluation_dirs.append(evaluation_dir)
        if candidate.candidate_id in SUPPORTED_AAPL_RESEARCH_CANDIDATES:
            trial_id = _next_trial_id(candidate, evaluation_dir)
            artifacts = _run_supported_candidate(
                candidate, evaluation_dir, trial_id
            )
            status = ResearchTrialStatus.SUCCEEDED
            message = "research simulation completed"
        else:
            trial_id = _next_trial_id(candidate, evaluation_dir)
            artifacts = ()
            status = ResearchTrialStatus.ABANDONED
            message = (
                "candidate implementation is not available in this stage; "
                "recorded without simulation"
            )

        append_research_trial(
            ResearchTrialRecord(
                trial_id=trial_id,
                research_family_id=candidate.research_family_id,
                candidate_id=candidate.candidate_id,
                status=status,
                started_at=started_at,
                completed_at=started_at,
                message=message,
                artifact_paths=artifacts,
            ),
            evaluation_dir,
        )

    return tuple(evaluation_dirs)


def _run_supported_candidate(
    candidate: StrategyCandidateSpec,
    evaluation_dir: Path,
    trial_id: str,
) -> tuple[str, ...]:
    scenario = candidate.simulation_scenarios[0]
    backtester = VectorBTBacktester(
        BacktestConfig(
            initial_cash=scenario.initial_cash,
            fees=scenario.fees,
        )
    )
    output_dir = evaluation_dir / "backtests" / trial_id
    extra_artifacts: tuple[str, ...] = ()

    if candidate.candidate_id == "aapl-momentum-baseline-5-20-v1":
        prices = load_price_csv(
            _input_path(candidate, ResearchInputKind.MARKET_BARS), "AAPL"
        )
        result, trades = backtester.run_with_trades(
            MomentumStrategy(
                MomentumConfig(
                    fast_window=_int_parameter(candidate, "fast_window"),
                    slow_window=_int_parameter(candidate, "slow_window"),
                )
            ),
            prices,
        )
    elif candidate.candidate_id == "aapl-feature-momentum-baseline-5-20-v1":
        features = load_feature_csv(
            _input_path(candidate, ResearchInputKind.FEATURES), "AAPL"
        )
        result, trades = backtester.run_feature_with_trades(
            FeatureMomentumStrategy(
                FeatureMomentumConfig(
                    fast_column=_str_parameter(candidate, "fast_column"),
                    slow_column=_str_parameter(candidate, "slow_column"),
                )
            ),
            features,
        )
    elif candidate.candidate_id == "aapl-target-native-trend-5-20-v1":
        prices = load_price_csv(
            _input_path(candidate, ResearchInputKind.MARKET_BARS), "AAPL"
        )
        result, trades, targets = VectorBTTargetBacktester(
            BacktestConfig(
                initial_cash=scenario.initial_cash,
                fees=scenario.fees,
            )
        ).run_with_trades(
            TargetNativeTrendStrategy(
                TargetNativeTrendConfig(
                    fast_window=_int_parameter(candidate, "fast_window"),
                    slow_window=_int_parameter(candidate, "slow_window"),
                    long_target_shares=_decimal_parameter(
                        candidate, "long_target_shares"
                    ),
                    short_target_shares=_decimal_parameter(
                        candidate, "short_target_shares"
                    ),
                )
            ),
            prices,
        )
        extra_artifacts = (
            str(write_target_frame(targets, output_dir / "targets.csv")),
        )
    elif candidate.candidate_id == "aapl-vol-adjusted-trend-5-20-20-v1":
        prices = load_price_csv(
            _input_path(candidate, ResearchInputKind.MARKET_BARS), "AAPL"
        )
        result, trades, targets = VectorBTTargetBacktester(
            BacktestConfig(
                initial_cash=scenario.initial_cash,
                fees=scenario.fees,
            )
        ).run_with_trades(
            VolatilityAdjustedTrendStrategy(
                VolatilityAdjustedTrendConfig(
                    fast_window=_int_parameter(candidate, "fast_window"),
                    slow_window=_int_parameter(candidate, "slow_window"),
                    volatility_window=_int_parameter(
                        candidate, "volatility_window"
                    ),
                    base_target_shares=_decimal_parameter(
                        candidate, "base_target_shares"
                    ),
                    min_target_shares=_decimal_parameter(
                        candidate, "min_target_shares"
                    ),
                    max_target_shares=_decimal_parameter(
                        candidate, "max_target_shares"
                    ),
                )
            ),
            prices,
        )
        extra_artifacts = (
            str(write_target_frame(targets, output_dir / "targets.csv")),
        )
    elif candidate.candidate_id == "aapl-mean-reversion-counterweight-5-20-v1":
        prices = load_price_csv(
            _input_path(candidate, ResearchInputKind.MARKET_BARS), "AAPL"
        )
        result, trades, targets = VectorBTTargetBacktester(
            BacktestConfig(
                initial_cash=scenario.initial_cash,
                fees=scenario.fees,
            )
        ).run_with_trades(
            MeanReversionCounterweightStrategy(
                MeanReversionCounterweightConfig(
                    lookback_window=_int_parameter(
                        candidate, "lookback_window"
                    ),
                    entry_zscore=_decimal_parameter(candidate, "entry_zscore"),
                    exit_zscore=_decimal_parameter(candidate, "exit_zscore"),
                    target_shares=_decimal_parameter(
                        candidate, "target_shares"
                    ),
                )
            ),
            prices,
        )
        extra_artifacts = (
            str(write_target_frame(targets, output_dir / "targets.csv")),
        )
    else:
        raise ValueError(f"unsupported candidate: {candidate.candidate_id}")

    paths = write_backtest_artifacts(result, trades, output_dir)
    return (paths.summary_json, paths.trades_csv, *extra_artifacts)


def _input_path(
    candidate: StrategyCandidateSpec, kind: ResearchInputKind
) -> Path:
    for input_snapshot in candidate.inputs:
        if input_snapshot.kind == kind:
            return Path(input_snapshot.path)
    raise ValueError(f"candidate lacks required input kind: {kind.value}")


def _int_parameter(candidate: StrategyCandidateSpec, name: str) -> int:
    value = _parameter(candidate, name)
    if not isinstance(value, int):
        raise ValueError(f"candidate parameter {name} must be an int")
    return value


def _decimal_parameter(candidate: StrategyCandidateSpec, name: str) -> Decimal:
    value = _parameter(candidate, name)
    if not isinstance(value, int | float | str):
        raise ValueError(f"candidate parameter {name} must be numeric")
    return Decimal(str(value))


def _str_parameter(candidate: StrategyCandidateSpec, name: str) -> str:
    value = _parameter(candidate, name)
    if not isinstance(value, str):
        raise ValueError(f"candidate parameter {name} must be a string")
    return value


def _parameter(candidate: StrategyCandidateSpec, name: str) -> object:
    for parameter in candidate.parameters:
        if parameter.name == name:
            return parameter.value
    raise ValueError(f"candidate missing parameter: {name}")


def _get_or_create_evaluation_dir(
    *,
    candidate: StrategyCandidateSpec,
    environment: ResearchEnvironmentSnapshot,
    output_root: Path,
) -> Path:
    evaluation_id = build_evaluation_id(candidate, environment)
    evaluation_dir = output_root / candidate.candidate_id / evaluation_id
    if evaluation_dir.exists():
        verify_evaluation_artifacts(evaluation_dir)
        return evaluation_dir
    paths = create_evaluation_artifacts(candidate, environment, output_root)
    return Path(paths.output_dir)


def _next_trial_id(
    candidate: StrategyCandidateSpec,
    evaluation_dir: Path,
) -> str:
    existing = load_research_trials(evaluation_dir / "trials.jsonl")
    return f"{candidate.candidate_id}-trial-v{len(existing) + 1}"
