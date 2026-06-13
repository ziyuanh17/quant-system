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


class PortfolioTargetStatus(StrEnum):
    AGGREGATED = "aggregated"
    BLOCKED = "blocked"


class RiskTargetStatus(StrEnum):
    APPROVED = "approved"
    REJECTED = "rejected"


class ContributionStatus(StrEnum):
    INCLUDED = "included"
    MISSING = "missing"
    DUPLICATE = "duplicate"
    NOT_YET_EFFECTIVE = "not_yet_effective"
    EXPIRED = "expired"
    STALE = "stale"
    UNAVAILABLE = "unavailable"
    SYMBOL_MISMATCH = "symbol_mismatch"
    UNIT_MISMATCH = "unit_mismatch"


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


class ContributorSpec(FrozenModel):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)


class ContributorSet(FrozenModel):
    """Immutable ownership and aggregation policy for one portfolio target."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    contributor_set_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    symbol: str = Field(min_length=1)
    unit: TargetUnit
    expected_contributors: tuple[ContributorSpec, ...] = Field(min_length=1)
    max_age_seconds: int = Field(gt=0)
    portfolio_policy_version: str = Field(min_length=1)
    reason: str = Field(min_length=1)

    @field_validator("expected_contributors")
    @classmethod
    def contributors_must_be_unique(
        cls, contributors: tuple[ContributorSpec, ...]
    ) -> tuple[ContributorSpec, ...]:
        identities = [
            (item.strategy_id, item.strategy_version) for item in contributors
        ]
        if len(identities) != len(set(identities)):
            raise ValueError("expected contributors must be unique")
        return contributors


class TargetContributionEvaluation(FrozenModel):
    strategy_id: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    matched_decision_ids: tuple[str, ...] = ()
    decision_id: str | None = None
    effective_status: TargetEffectiveStatus | None = None
    contribution_status: ContributionStatus
    target_value: Decimal | None = None
    reason: str = Field(min_length=1)

    @model_validator(mode="after")
    def included_contribution_must_be_complete(
        self,
    ) -> "TargetContributionEvaluation":
        if self.contribution_status == ContributionStatus.INCLUDED:
            if (
                self.decision_id is None
                or self.matched_decision_ids != (self.decision_id,)
                or self.effective_status != TargetEffectiveStatus.ACTIVE
                or self.target_value is None
            ):
                raise ValueError(
                    "included contributions require active decision and value"
                )
        elif self.target_value is not None:
            raise ValueError(
                "non-included contributions must not have target_value"
            )
        if (
            self.contribution_status == ContributionStatus.MISSING
            and self.matched_decision_ids
        ):
            raise ValueError("missing contributions must not match decisions")
        if (
            self.contribution_status == ContributionStatus.DUPLICATE
            and len(self.matched_decision_ids) < 2
        ):
            raise ValueError(
                "duplicate contributions require all matching decision IDs"
            )
        return self


class PortfolioTargetDecision(FrozenModel):
    """Deterministic aggregate or explicit blocked aggregation result."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    portfolio_target_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    contributor_set_id: str = Field(min_length=1)
    contributor_set_revision: int = Field(ge=1)
    portfolio_policy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    unit: TargetUnit
    generated_at: datetime
    evaluated_at: datetime
    status: PortfolioTargetStatus
    aggregate_value: Decimal | None = None
    contributing_decision_ids: tuple[str, ...] = ()
    contribution_evaluations: tuple[TargetContributionEvaluation, ...] = Field(
        min_length=1
    )
    reason: str = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_aggregation_result(self) -> "PortfolioTargetDecision":
        included_ids = tuple(
            item.decision_id
            for item in self.contribution_evaluations
            if item.contribution_status == ContributionStatus.INCLUDED
        )
        if self.status == PortfolioTargetStatus.AGGREGATED:
            if self.aggregate_value is None:
                raise ValueError("aggregated portfolio targets require value")
            if len(included_ids) != len(self.contribution_evaluations):
                raise ValueError(
                    "aggregated portfolio targets require all contributors"
                )
            if self.contributing_decision_ids != included_ids:
                raise ValueError(
                    "contributing decision IDs must match included evaluations"
                )
            included_total = sum(
                (
                    item.target_value
                    for item in self.contribution_evaluations
                    if item.target_value is not None
                ),
                Decimal("0"),
            )
            if self.aggregate_value != included_total:
                raise ValueError(
                    "aggregate value must equal included contribution values"
                )
        elif self.aggregate_value is not None or self.contributing_decision_ids:
            raise ValueError(
                "blocked portfolio targets must not carry aggregate value "
                "or IDs"
            )
        return self


class ResearchRiskPolicy(FrozenModel):
    risk_policy_version: str = Field(min_length=1)
    allow_short_targets: bool = True
    max_absolute_target: Decimal | None = Field(default=None, gt=0)


class RiskTargetDecision(FrozenModel):
    """Independent approval or rejection of a portfolio target."""

    schema_version: Literal[1] = TARGET_SCHEMA_VERSION
    risk_target_id: str = Field(min_length=1)
    revision: int = Field(ge=1)
    portfolio_target_id: str = Field(min_length=1)
    risk_policy_version: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    unit: TargetUnit
    generated_at: datetime
    evaluated_at: datetime
    status: RiskTargetStatus
    approved_target_value: Decimal | None = None
    reasons: tuple[str, ...] = Field(min_length=1)
    evidence_refs: tuple[str, ...] = ()

    @model_validator(mode="after")
    def validate_risk_result(self) -> "RiskTargetDecision":
        if (
            self.status == RiskTargetStatus.APPROVED
            and self.approved_target_value is None
        ):
            raise ValueError("approved risk targets require target value")
        if (
            self.status == RiskTargetStatus.REJECTED
            and self.approved_target_value is not None
        ):
            raise ValueError("rejected risk targets must not have target value")
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
