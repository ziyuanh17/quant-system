"""Run supported research candidates from reviewed batch artifacts."""

from datetime import datetime
from pathlib import Path

from quant.backtest import VectorBTBacktester
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
    create_evaluation_artifacts,
    load_research_batch_spec,
    verify_research_batch_artifacts,
)
from quant.strategies import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
    MomentumConfig,
    MomentumStrategy,
)

SUPPORTED_AAPL_RESEARCH_CANDIDATES = (
    "aapl-momentum-baseline-5-20-v1",
    "aapl-feature-momentum-baseline-5-20-v1",
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
        paths = create_evaluation_artifacts(
            candidate, environment, output_root
        )
        evaluation_dir = Path(paths.output_dir)
        evaluation_dirs.append(evaluation_dir)
        if candidate.candidate_id in SUPPORTED_AAPL_RESEARCH_CANDIDATES:
            artifacts = _run_supported_candidate(candidate, evaluation_dir)
            status = ResearchTrialStatus.SUCCEEDED
            message = "research simulation completed"
        else:
            artifacts = ()
            status = ResearchTrialStatus.ABANDONED
            message = (
                "candidate implementation is not available in this stage; "
                "recorded without simulation"
            )

        append_research_trial(
            ResearchTrialRecord(
                trial_id=f"{candidate.candidate_id}-trial-v1",
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
) -> tuple[str, ...]:
    scenario = candidate.simulation_scenarios[0]
    backtester = VectorBTBacktester(
        BacktestConfig(
            initial_cash=scenario.initial_cash,
            fees=scenario.fees,
        )
    )
    output_dir = evaluation_dir / "backtest"

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
    else:
        raise ValueError(f"unsupported candidate: {candidate.candidate_id}")

    paths = write_backtest_artifacts(result, trades, output_dir)
    return (paths.summary_json, paths.trades_csv)


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
