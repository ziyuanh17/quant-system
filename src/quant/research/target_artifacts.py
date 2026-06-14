"""Persist schema-versioned semantic-target research artifacts."""

import json
import os
from pathlib import Path

import pandas as pd
from pydantic import BaseModel

from quant.models.targets import (
    TARGET_SCHEMA_VERSION,
    ContributorSet,
    LegacyEquivalenceReport,
    PortfolioTargetDecision,
    RiskTargetDecision,
    StrategyEvaluation,
    StrategyTargetDecision,
    StrategyTargetFrame,
    TargetBacktestEvidence,
)


def write_contributor_set(
    contributor_set: ContributorSet,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root
        / contributor_set.contributor_set_id
        / f"{contributor_set.revision}.json",
        contributor_set,
    )


def load_contributor_set(path: Path) -> ContributorSet:
    return ContributorSet.model_validate_json(path.read_text())


def write_portfolio_target_decision(
    decision: PortfolioTargetDecision,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root
        / decision.portfolio_target_id
        / f"{decision.revision}.json",
        decision,
    )


def load_portfolio_target_decision(path: Path) -> PortfolioTargetDecision:
    return PortfolioTargetDecision.model_validate_json(path.read_text())


def write_risk_target_decision(
    decision: RiskTargetDecision,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root / decision.risk_target_id / f"{decision.revision}.json",
        decision,
    )


def load_risk_target_decision(path: Path) -> RiskTargetDecision:
    return RiskTargetDecision.model_validate_json(path.read_text())


def write_strategy_target_decision(
    decision: StrategyTargetDecision,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root / decision.strategy_id / f"{decision.decision_id}.json",
        decision,
    )


def load_strategy_target_decision(path: Path) -> StrategyTargetDecision:
    return StrategyTargetDecision.model_validate_json(path.read_text())


def write_strategy_evaluation(
    evaluation: StrategyEvaluation,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root
        / evaluation.strategy_id
        / f"{evaluation.evaluation_id}.json",
        evaluation,
    )


def load_strategy_evaluation(path: Path) -> StrategyEvaluation:
    return StrategyEvaluation.model_validate_json(path.read_text())


def write_legacy_equivalence_report(
    report: LegacyEquivalenceReport,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root / f"{report.report_id}.json", report
    )


def load_legacy_equivalence_report(path: Path) -> LegacyEquivalenceReport:
    return LegacyEquivalenceReport.model_validate_json(path.read_text())


def write_target_backtest_evidence(
    evidence: TargetBacktestEvidence,
    output_root: Path,
) -> Path:
    return _write_model_exclusive(
        output_root / f"{evidence.evidence_id}.json", evidence
    )


def load_target_backtest_evidence(path: Path) -> TargetBacktestEvidence:
    return TargetBacktestEvidence.model_validate_json(path.read_text())


def write_target_frame(frame: StrategyTargetFrame, path: Path) -> Path:
    payload = pd.DataFrame(
        {
            "schema_version": TARGET_SCHEMA_VERSION,
            "timestamp": frame.targets.index,
            "unit": frame.unit.value,
            "target_value": [str(value) for value in frame.targets],
        }
    ).to_csv(index=False)
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(path, payload.encode())
    return path


def load_target_frame(path: Path) -> StrategyTargetFrame:
    payload = pd.read_csv(path)
    required = {"schema_version", "timestamp", "unit", "target_value"}
    if set(payload.columns) != required:
        raise ValueError("target frame artifact has unexpected columns")
    versions = tuple(payload["schema_version"].unique())
    if versions != (TARGET_SCHEMA_VERSION,):
        raise ValueError("unsupported target frame schema version")
    units = tuple(payload["unit"].unique())
    if len(units) != 1:
        raise ValueError("target frame artifact must contain exactly one unit")
    targets = pd.Series(
        payload["target_value"].tolist(),
        index=pd.DatetimeIndex(pd.to_datetime(payload["timestamp"])),
        dtype=object,
    )
    return StrategyTargetFrame(unit=units[0], targets=targets)


def _write_model_exclusive(path: Path, model: BaseModel) -> Path:
    payload = (
        json.dumps(model.model_dump(mode="json"), indent=2, sort_keys=True)
        + "\n"
    ).encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    _write_exclusive(path, payload)
    return path


def _write_exclusive(path: Path, payload: bytes) -> None:
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    try:
        os.write(descriptor, payload)
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
