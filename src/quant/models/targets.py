from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Literal, cast

import pandas as pd
from pydantic import Field, ValidationInfo, field_validator, model_validator

from quant.models.base import FrozenModel

TARGET_SCHEMA_VERSION = 1


class TargetUnit(StrEnum):
    SHARES = "shares"
    WEIGHT = "weight"
    NOTIONAL = "notional"


class TargetDeclaredStatus(StrEnum):
    ACTIVE = "active"
    UNAVAILABLE = "unavailable"


class TargetEffectiveStatus(StrEnum):
    ACTIVE = "active"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    STALE = "stale"
    UNAVAILABLE = "unavailable"


class StrategyEvaluationOutcome(StrEnum):
    NEW_TARGET = "new_target"
    NO_CHANGE = "no_change"
    UNAVAILABLE = "unavailable"


class StrategyTargetFrame(FrozenModel):
    """Timestamp-aligned decimal strategy targets for research."""

    unit: TargetUnit
    targets: pd.Series

    @field_validator("targets")
    @classmethod
    def targets_must_be_numeric_and_complete(
        cls, targets: pd.Series
    ) -> pd.Series:
        if not isinstance(targets.index, pd.DatetimeIndex):
            raise ValueError("target index must be a DatetimeIndex")
        if not targets.index.is_monotonic_increasing:
            raise ValueError("target index must be monotonic increasing")
        if not targets.index.is_unique:
            raise ValueError("target index must be unique")
        numeric = cast(pd.Series, pd.to_numeric(targets, errors="coerce"))
        if numeric.isna().any():
            raise ValueError(
                "targets must be numeric and contain no missing values"
            )
        return pd.Series(
            [Decimal(str(value)) for value in numeric],
            index=targets.index,
            dtype=object,
            name=targets.name,
        )


class StrategyTargetDecision(FrozenModel):
    """Immutable strategy target revision."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    decision_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    unit: TargetUnit
    target_value: Decimal | None = None
    sizing_policy_version: str = Field(min_length=1)
    input_data_id: str = Field(min_length=1)
    generated_at: datetime
    effective_at: datetime
    valid_until: datetime
    declared_status: TargetDeclaredStatus
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_target_revision(self) -> "StrategyTargetDecision":
        if self.valid_until <= self.effective_at:
            raise ValueError("valid_until must be after effective_at")
        if (
            self.declared_status == TargetDeclaredStatus.ACTIVE
            and self.target_value is None
        ):
            raise ValueError("active target decisions require target_value")
        if (
            self.declared_status == TargetDeclaredStatus.UNAVAILABLE
            and self.target_value is not None
        ):
            raise ValueError(
                "unavailable target decisions must not have target_value"
            )
        return self


class StrategyEvaluation(FrozenModel):
    """One strategy observation, separate from immutable target revisions."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    evaluation_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    evaluated_at: datetime
    outcome: StrategyEvaluationOutcome
    effective_target_decision_id: str | None = None
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def require_effective_target_when_available(self) -> "StrategyEvaluation":
        if (
            self.outcome != StrategyEvaluationOutcome.UNAVAILABLE
            and self.effective_target_decision_id is None
        ):
            raise ValueError(
                "available evaluations require effective_target_decision_id"
            )
        if (
            self.outcome == StrategyEvaluationOutcome.UNAVAILABLE
            and self.effective_target_decision_id is not None
        ):
            raise ValueError(
                "unavailable evaluations must not reference a target decision"
            )
        return self


class TargetBacktestEvidence(FrozenModel):
    """Research evidence from a native target-amount simulation."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    evidence_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    unit: TargetUnit
    sizing_policy_version: str = Field(min_length=1)
    input_data_id: str = Field(min_length=1)
    target_artifact_path: str = Field(min_length=1)
    result_artifact_path: str = Field(min_length=1)


class LegacyEquivalenceStatus(StrEnum):
    EQUIVALENT = "equivalent"
    NOT_EQUIVALENT = "not_equivalent"


class LegacyEquivalenceReport(FrozenModel):
    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    report_id: str = Field(min_length=1)
    strategy_id: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    sizing_policy_version: str = Field(min_length=1)
    scenario_name: str = Field(min_length=1)
    status: LegacyEquivalenceStatus
    numeric_tolerance: float = Field(ge=0)
    baseline_total_return: float
    adapted_total_return: float
    baseline_final_value: float
    adapted_final_value: float
    baseline_trade_count: int = Field(ge=0)
    adapted_trade_count: int = Field(ge=0)
    comparison_dimensions: tuple[str, ...] = (
        "orders",
        "trades",
        "assets",
        "cash",
        "portfolio_value",
        "total_return",
        "final_value",
    )
    differences: tuple[str, ...] = ()


class TargetSimulationInput(FrozenModel):
    strategy_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    close: pd.Series
    targets: StrategyTargetFrame
    diagnostics: tuple[str, ...] = ()

    @field_validator("targets")
    @classmethod
    def targets_must_align_with_close(
        cls, targets: StrategyTargetFrame, info: ValidationInfo
    ) -> StrategyTargetFrame:
        close = info.data.get("close")
        if close is not None and not targets.targets.index.equals(close.index):
            raise ValueError("targets and close must share the same index")
        return targets
