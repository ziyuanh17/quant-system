from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import cast

import pandas as pd
import pytest
from pydantic import ValidationError

from quant.backtest import VectorBTTargetBacktester
from quant.models.backtest import BacktestConfig
from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.signals import SignalFrame
from quant.models.targets import (
    LegacyEquivalenceStatus,
    StrategyEvaluation,
    StrategyEvaluationOutcome,
    StrategyTargetDecision,
    StrategyTargetFrame,
    TargetBacktestEvidence,
    TargetDeclaredStatus,
    TargetEffectiveStatus,
    TargetUnit,
)
from quant.research import (
    FeatureTargetStrategySimulationAdapter,
    FixedSharesLegacyPriceAdapter,
    evaluate_target_effective_status,
    investigate_legacy_equivalence,
    load_legacy_equivalence_report,
    load_strategy_evaluation,
    load_strategy_target_decision,
    load_target_backtest_evidence,
    load_target_frame,
    require_operational_whole_share_targets,
    write_legacy_equivalence_report,
    write_strategy_evaluation,
    write_strategy_target_decision,
    write_target_backtest_evidence,
    write_target_frame,
)


def test_target_frame_accepts_fractional_research_shares() -> None:
    frame = _target_frame(["0", "1.5", "-0.25"])

    assert frame.targets.tolist() == [
        Decimal("0.0"),
        Decimal("1.5"),
        Decimal("-0.25"),
    ]


def test_target_frame_rejects_missing_values_and_unaligned_index() -> None:
    with pytest.raises(ValidationError, match="no missing values"):
        StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(
                [0, None],
                index=pd.date_range("2024-01-01", periods=2),
            ),
        )
    with pytest.raises(ValidationError, match="monotonic increasing"):
        StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(
                [0, 1],
                index=pd.DatetimeIndex(["2024-01-02", "2024-01-01"]),
            ),
        )


def test_operational_capability_rejects_fractional_without_rounding() -> None:
    fractional = _target_frame(["0", "1.5"])

    with pytest.raises(ValueError, match="cannot be fractional"):
        require_operational_whole_share_targets(fractional)

    whole = _target_frame(["0", "-2"])
    assert require_operational_whole_share_targets(whole) == whole


def test_target_decision_validates_declared_status_and_validity() -> None:
    with pytest.raises(ValidationError, match="require target_value"):
        _decision(target_value=None)
    with pytest.raises(ValidationError, match="must not have target_value"):
        _decision(declared_status=TargetDeclaredStatus.UNAVAILABLE)


def test_effective_status_is_derived_without_mutating_decision() -> None:
    decision = _decision()

    assert (
        evaluate_target_effective_status(
            decision,
            evaluated_at=decision.effective_at - timedelta(seconds=1),
            max_age=timedelta(hours=2),
        )
        == TargetEffectiveStatus.NOT_YET_EFFECTIVE
    )
    assert (
        evaluate_target_effective_status(
            decision,
            evaluated_at=decision.valid_until + timedelta(seconds=1),
            max_age=timedelta(days=2),
        )
        == TargetEffectiveStatus.EXPIRED
    )
    assert (
        evaluate_target_effective_status(
            decision,
            evaluated_at=decision.generated_at + timedelta(hours=3),
            max_age=timedelta(hours=2),
        )
        == TargetEffectiveStatus.STALE
    )


def test_no_change_evaluation_references_effective_target() -> None:
    evaluation = StrategyEvaluation(
        evaluation_id="evaluation-1",
        strategy_id="native-target",
        strategy_version="1",
        symbol="AAPL",
        evaluated_at=datetime(2026, 6, 12, tzinfo=UTC),
        outcome=StrategyEvaluationOutcome.NO_CHANGE,
        effective_target_decision_id="decision-1",
        reason="target remains unchanged",
    )

    assert evaluation.effective_target_decision_id == "decision-1"
    with pytest.raises(ValidationError, match="require effective_target"):
        StrategyEvaluation(
            evaluation_id="evaluation-2",
            strategy_id="native-target",
            strategy_version="1",
            symbol="AAPL",
            evaluated_at=datetime(2026, 6, 12, tzinfo=UTC),
            outcome=StrategyEvaluationOutcome.NO_CHANGE,
            reason="invalid no-change observation",
        )


def test_unavailable_evaluation_cannot_reference_previous_target() -> None:
    with pytest.raises(ValidationError, match="must not reference"):
        StrategyEvaluation(
            evaluation_id="evaluation-unavailable",
            strategy_id="native-target",
            strategy_version="1",
            symbol="AAPL",
            evaluated_at=datetime(2026, 6, 12, tzinfo=UTC),
            outcome=StrategyEvaluationOutcome.UNAVAILABLE,
            effective_target_decision_id="decision-1",
            reason="input unavailable",
        )


def test_target_artifacts_are_immutable_and_round_trip(tmp_path) -> None:
    decision = _decision()
    evaluation = StrategyEvaluation(
        evaluation_id="evaluation-1",
        strategy_id=decision.strategy_id,
        strategy_version=decision.strategy_version,
        symbol=decision.symbol,
        evaluated_at=decision.generated_at,
        outcome=StrategyEvaluationOutcome.NEW_TARGET,
        effective_target_decision_id=decision.decision_id,
        reason="new target",
    )
    frame = _target_frame(["0", "1.5", "-1"])

    decision_path = write_strategy_target_decision(
        decision, tmp_path / "strategy-targets"
    )
    evaluation_path = write_strategy_evaluation(
        evaluation, tmp_path / "strategy-evaluations"
    )
    frame_path = write_target_frame(frame, tmp_path / "targets.csv")
    evidence = TargetBacktestEvidence(
        evidence_id="evidence-1",
        strategy_id=decision.strategy_id,
        symbol=decision.symbol,
        unit=TargetUnit.SHARES,
        sizing_policy_version=decision.sizing_policy_version,
        input_data_id=decision.input_data_id,
        target_artifact_path=str(frame_path),
        result_artifact_path="data/results/target-summary.json",
    )
    evidence_path = write_target_backtest_evidence(
        evidence, tmp_path / "target-backtests"
    )

    assert load_strategy_target_decision(decision_path) == decision
    assert load_strategy_evaluation(evaluation_path) == evaluation
    loaded_frame = load_target_frame(frame_path)
    assert loaded_frame.unit == frame.unit
    assert loaded_frame.targets.equals(frame.targets)
    assert load_target_backtest_evidence(evidence_path) == evidence
    with pytest.raises(FileExistsError):
        write_strategy_target_decision(decision, tmp_path / "strategy-targets")


def test_fixed_share_adapter_carries_target_between_events() -> None:
    prices = _prices()
    adapter = FixedSharesLegacyPriceAdapter(
        _LegacyStrategy(), shares=Decimal("2.5")
    )

    output = adapter.build(prices)

    assert output.targets.targets.tolist() == [
        Decimal("0"),
        Decimal("2.5"),
        Decimal("2.5"),
        Decimal("0"),
        Decimal("0"),
    ]


def test_native_target_backtest_supports_reversals() -> None:
    prices = _prices()

    result, trades, targets = VectorBTTargetBacktester(
        BacktestConfig(initial_cash=10_000, fees=0)
    ).run_with_trades(_NativeTargetStrategy(), prices)

    assert targets.targets.tolist() == [
        Decimal("0"),
        Decimal("2"),
        Decimal("-1"),
        Decimal("0"),
        Decimal("1.5"),
    ]
    assert result.metrics.total_trades >= 3
    assert not trades.empty


def test_native_feature_target_adapter_builds_aligned_targets() -> None:
    features = FeatureData(
        symbol="AAPL",
        frame=cast(
            pd.DataFrame,
            _prices().frame[["date", "symbol", "close"]],
        ),
    )

    output = FeatureTargetStrategySimulationAdapter(
        _NativeFeatureTargetStrategy()
    ).build(features)

    assert output.targets.targets.index.equals(features.close.index)
    assert output.targets.targets.iloc[-1] == Decimal("-1")


def test_legacy_equivalence_investigation_reports_evidence(tmp_path) -> None:
    prices = _prices()
    signals = _LegacyStrategy().generate_signals(prices)

    report = investigate_legacy_equivalence(
        report_id="equivalence-base",
        strategy_id="legacy",
        symbol=prices.symbol,
        scenario_name="base-no-fees",
        close=prices.close,
        signals=signals,
        initial_cash=10_000,
        fees=0,
    )
    path = write_legacy_equivalence_report(
        report, tmp_path / "legacy-equivalence"
    )

    assert report.status in {
        LegacyEquivalenceStatus.EQUIVALENT,
        LegacyEquivalenceStatus.NOT_EQUIVALENT,
    }
    assert path.exists()
    assert load_legacy_equivalence_report(path) == report
    with pytest.raises(FileExistsError):
        write_legacy_equivalence_report(report, tmp_path / "legacy-equivalence")


@pytest.mark.parametrize(
    ("name", "entries", "exits", "fees", "slippage", "accumulate"),
    [
        (
            "same-bar",
            [False, True, False, False, False],
            [False, False, False, True, False],
            0.0,
            0.0,
            False,
        ),
        (
            "fees-and-slippage",
            [False, True, False, False, False],
            [False, False, False, True, False],
            0.001,
            0.002,
            False,
        ),
        (
            "repeated-entry-accumulation",
            [False, True, True, False, False],
            [False, False, False, True, False],
            0.0,
            0.0,
            True,
        ),
        (
            "insufficient-cash-pressure",
            [True, False, False, False, False],
            [False, False, False, False, True],
            0.05,
            0.0,
            False,
        ),
    ],
)
def test_legacy_equivalence_scenarios_are_classified(
    name,
    entries,
    exits,
    fees,
    slippage,
    accumulate,
) -> None:
    prices = _prices()
    signals = SignalFrame(
        entries=pd.Series(entries, index=prices.close.index),
        exits=pd.Series(exits, index=prices.close.index),
    )

    report = investigate_legacy_equivalence(
        report_id=f"report-{name}",
        strategy_id="legacy",
        symbol=prices.symbol,
        scenario_name=name,
        close=prices.close,
        signals=signals,
        initial_cash=100,
        fees=fees,
        slippage=slippage,
        accumulate=accumulate,
    )

    assert report.scenario_name == name
    assert isinstance(report.status, LegacyEquivalenceStatus)


class _LegacyStrategy:
    name = "legacy"

    def generate_signals(self, prices: PriceData) -> SignalFrame:
        index = prices.close.index
        return SignalFrame(
            entries=pd.Series([False, True, False, False, False], index=index),
            exits=pd.Series([False, False, False, True, False], index=index),
        )


class _NativeTargetStrategy:
    name = "native-target"

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame:
        return StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(
                [
                    Decimal("0"),
                    Decimal("2"),
                    Decimal("-1"),
                    Decimal("0"),
                    Decimal("1.5"),
                ],
                index=prices.close.index,
                dtype=object,
            ),
        )


class _NativeFeatureTargetStrategy:
    name = "native-feature-target"

    def generate_targets_from_features(
        self, features: FeatureData
    ) -> StrategyTargetFrame:
        return StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(
                [
                    Decimal("0"),
                    Decimal("1"),
                    Decimal("1"),
                    Decimal("0"),
                    Decimal("-1"),
                ],
                index=features.close.index,
                dtype=object,
            ),
        )


def _decision(
    *,
    target_value: Decimal | None = Decimal("-2"),
    declared_status: TargetDeclaredStatus = TargetDeclaredStatus.ACTIVE,
) -> StrategyTargetDecision:
    generated_at = datetime(2026, 6, 12, 12, tzinfo=UTC)
    return StrategyTargetDecision(
        decision_id="decision-1",
        revision=1,
        strategy_id="native-target",
        strategy_version="1",
        symbol="AAPL",
        unit=TargetUnit.SHARES,
        target_value=target_value,
        sizing_policy_version="native_targets_v1",
        input_data_id="bars-sha256",
        generated_at=generated_at,
        effective_at=generated_at + timedelta(minutes=1),
        valid_until=generated_at + timedelta(days=1),
        declared_status=declared_status,
        reason="research target",
    )


def _target_frame(values: list[str]) -> StrategyTargetFrame:
    return StrategyTargetFrame(
        unit=TargetUnit.SHARES,
        targets=pd.Series(
            values,
            index=pd.date_range("2024-01-01", periods=len(values)),
            dtype=object,
        ),
    )


def _prices() -> PriceData:
    dates = [item.date() for item in pd.date_range("2024-01-01", periods=5)]
    close = [10.0, 11.0, 12.0, 9.0, 10.0]
    return PriceData(
        symbol="AAPL",
        frame=pd.DataFrame(
            {
                "date": dates,
                "symbol": ["AAPL"] * 5,
                "open": close,
                "high": [value + 1 for value in close],
                "low": [value - 1 for value in close],
                "close": close,
                "volume": [100] * 5,
            }
        ),
    )
