"""Define research candidate, policy, and evaluation-evidence models."""

from datetime import date, datetime
from enum import StrEnum
from typing import Literal

import pandas as pd
from pydantic import Field, ValidationInfo, field_validator, model_validator

from quant.models.base import FrozenModel
from quant.models.signals import SignalFrame


class ResearchInputKind(StrEnum):
    MARKET_BARS = "market_bars"
    FEATURES = "features"
    UNIVERSE = "universe"
    BENCHMARK = "benchmark"


class PointInTimePolicy(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    EVENT_TIME_ONLY = "event_time_only"
    EVENT_AND_AVAILABILITY_TIME = "event_and_availability_time"


class ResearchTrialStatus(StrEnum):
    PLANNED = "planned"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ABANDONED = "abandoned"


class ResearchComparisonRole(StrEnum):
    DECLARED_POLICY = "declared_policy"
    SIZING_ABLATION = "sizing_ablation"


class ResearchDecisionOutcome(StrEnum):
    PASS_AS_CONTROL = "pass_as_control"
    PASS_FOR_PARITY = "pass_for_parity"
    FAIL_PROMOTION = "fail_promotion"


class ResearchEnvironmentSnapshot(FrozenModel):
    """Reproducibility identity for the code environment running evaluation."""

    source_commit: str = Field(min_length=1)
    dependency_lock_sha256: str
    python_version: str = Field(min_length=1)
    platform: str = Field(min_length=1)
    evaluator_version: str = Field(min_length=1)

    @field_validator("dependency_lock_sha256")
    @classmethod
    def dependency_hash_must_be_lowercase_hex(cls, value: str) -> str:
        return _validate_sha256(value)


class ResearchParameter(FrozenModel):
    """One explicit, serializable strategy or evaluator parameter."""

    name: str = Field(min_length=1)
    value: str | int | float | bool


class ResearchInputSnapshot(FrozenModel):
    """Immutable identity and point-in-time policy for one research input."""

    input_id: str = Field(min_length=1)
    kind: ResearchInputKind
    path: str = Field(min_length=1)
    sha256: str
    schema_version: str = Field(min_length=1)
    event_time_column: str | None = None
    availability_time_column: str | None = None
    point_in_time_policy: PointInTimePolicy = PointInTimePolicy.EVENT_TIME_ONLY

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_lowercase_hex(cls, value: str) -> str:
        return _validate_sha256(value)

    @model_validator(mode="after")
    def availability_policy_must_have_column(self) -> "ResearchInputSnapshot":
        if (
            self.point_in_time_policy
            == PointInTimePolicy.EVENT_AND_AVAILABILITY_TIME
            and self.availability_time_column is None
        ):
            raise ValueError(
                "availability_time_column is required for "
                "event-and-availability-time policy"
            )
        return self


class EvaluationSplitPolicy(FrozenModel):
    """Ordered, non-overlapping development, validation, and holdout periods."""

    development_start: date
    development_end: date
    validation_start: date
    validation_end: date
    holdout_start: date
    holdout_end: date

    @model_validator(mode="after")
    def periods_must_be_ordered_and_non_overlapping(
        self,
    ) -> "EvaluationSplitPolicy":
        if not (
            self.development_start <= self.development_end
            < self.validation_start
            <= self.validation_end
            < self.holdout_start
            <= self.holdout_end
        ):
            raise ValueError(
                "evaluation periods must be ordered and non-overlapping"
            )
        return self


class SimulationScenario(FrozenModel):
    """Versioned assumptions applied by a simulation engine."""

    name: str = Field(min_length=1)
    initial_cash: float = Field(default=100_000, gt=0)
    fees: float = Field(default=0.001, ge=0)
    slippage_bps: float = Field(default=0, ge=0)
    execution_delay_bars: int = Field(default=0, ge=0)
    max_participation_rate: float | None = Field(default=None, gt=0, le=1)


class StrategyCandidateSpec(FrozenModel):
    """Complete identity and declared evaluation policy for one candidate."""

    candidate_id: str = Field(min_length=1)
    research_family_id: str = Field(min_length=1)
    hypothesis_id: str = Field(min_length=1)
    hypothesis: str = Field(min_length=1)
    strategy_name: str = Field(min_length=1)
    strategy_version: str = Field(min_length=1)
    parameters: tuple[ResearchParameter, ...] = ()
    symbols: tuple[str, ...] = Field(min_length=1)
    inputs: tuple[ResearchInputSnapshot, ...] = Field(min_length=1)
    split_policy: EvaluationSplitPolicy
    simulation_scenarios: tuple[SimulationScenario, ...] = Field(min_length=1)
    benchmark_name: str = Field(min_length=1)
    promotion_criteria_version: str = Field(min_length=1)
    comparison_role: ResearchComparisonRole = (
        ResearchComparisonRole.DECLARED_POLICY
    )
    promotion_eligible: bool = True
    source_commit: str = Field(min_length=1)
    dependency_lock_sha256: str
    random_seed: int | None = None

    @field_validator("dependency_lock_sha256")
    @classmethod
    def dependency_hash_must_be_lowercase_hex(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("parameters")
    @classmethod
    def parameter_names_must_be_unique(
        cls, parameters: tuple[ResearchParameter, ...]
    ) -> tuple[ResearchParameter, ...]:
        _require_unique(
            tuple(parameter.name for parameter in parameters),
            "parameter names",
        )
        return parameters

    @field_validator("symbols")
    @classmethod
    def symbols_must_be_unique(
        cls, symbols: tuple[str, ...]
    ) -> tuple[str, ...]:
        _require_unique(symbols, "symbols")
        return symbols

    @field_validator("inputs")
    @classmethod
    def input_ids_must_be_unique(
        cls, inputs: tuple[ResearchInputSnapshot, ...]
    ) -> tuple[ResearchInputSnapshot, ...]:
        _require_unique(tuple(item.input_id for item in inputs), "input IDs")
        return inputs

    @field_validator("simulation_scenarios")
    @classmethod
    def scenario_names_must_be_unique(
        cls, scenarios: tuple[SimulationScenario, ...]
    ) -> tuple[SimulationScenario, ...]:
        _require_unique(
            tuple(scenario.name for scenario in scenarios),
            "scenario names",
        )
        return scenarios

    @model_validator(mode="after")
    def sizing_ablations_are_not_promotion_eligible(
        self,
    ) -> "StrategyCandidateSpec":
        if (
            self.comparison_role == ResearchComparisonRole.SIZING_ABLATION
            and self.promotion_eligible
        ):
            raise ValueError(
                "sizing-ablation candidates must not be promotion eligible"
            )
        return self


class ResearchBatchSpec(FrozenModel):
    """Reviewed group of strategy candidates for one research-only batch."""

    schema_version: Literal[1] = 1
    batch_id: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    symbols: tuple[str, ...] = Field(min_length=1)
    candidates: tuple[StrategyCandidateSpec, ...] = Field(min_length=1)
    evidence_required: tuple[str, ...] = Field(min_length=1)
    stop_conditions: tuple[str, ...] = Field(min_length=1)
    created_at: datetime
    broker_access_authorized: Literal[False] = False
    runtime_mutation_authorized: Literal[False] = False
    scheduler_authorized: Literal[False] = False
    order_submission_authorized: Literal[False] = False

    @field_validator("symbols")
    @classmethod
    def batch_symbols_must_be_unique(
        cls, symbols: tuple[str, ...]
    ) -> tuple[str, ...]:
        _require_unique(symbols, "batch symbols")
        return symbols

    @field_validator("candidates")
    @classmethod
    def candidate_ids_must_be_unique(
        cls, candidates: tuple[StrategyCandidateSpec, ...]
    ) -> tuple[StrategyCandidateSpec, ...]:
        _require_unique(
            tuple(candidate.candidate_id for candidate in candidates),
            "candidate IDs",
        )
        return candidates

    @model_validator(mode="after")
    def candidates_must_fit_batch_scope(self) -> "ResearchBatchSpec":
        batch_symbols = set(self.symbols)
        for candidate in self.candidates:
            unknown = set(candidate.symbols) - batch_symbols
            if unknown:
                joined = ", ".join(sorted(unknown))
                raise ValueError(
                    f"candidate {candidate.candidate_id} has symbols outside "
                    f"the batch scope: {joined}"
                )
        source_commits = {
            candidate.source_commit for candidate in self.candidates
        }
        if len(source_commits) != 1:
            raise ValueError("batch candidates must share one source commit")
        dependency_locks = {
            candidate.dependency_lock_sha256 for candidate in self.candidates
        }
        if len(dependency_locks) != 1:
            raise ValueError("batch candidates must share one dependency lock")
        return self


class ResearchOperationalAuthorization(FrozenModel):
    """Explicit non-operational permissions carried by a research decision."""

    alpaca_authorized: Literal[False] = False
    broker_authorized: Literal[False] = False
    dry_run_authorized: Literal[False] = False
    order_submission_authorized: Literal[False] = False
    paper_trading_authorized: Literal[False] = False
    runtime_mutation_authorized: Literal[False] = False
    scheduler_authorized: Literal[False] = False


class ResearchCandidateDecision(FrozenModel):
    """Pass/fail outcome for one research candidate in a report."""

    candidate_id: str = Field(min_length=1)
    decision: ResearchDecisionOutcome
    reason: str = Field(min_length=1)
    comparison_role: ResearchComparisonRole = (
        ResearchComparisonRole.DECLARED_POLICY
    )
    promotion_eligible: bool = True

    @model_validator(mode="after")
    def sizing_ablations_are_not_promotion_eligible(
        self,
    ) -> "ResearchCandidateDecision":
        if (
            self.comparison_role == ResearchComparisonRole.SIZING_ABLATION
            and self.promotion_eligible
        ):
            raise ValueError(
                "sizing-ablation decisions must not be promotion eligible"
            )
        return self


class ResearchDecisionReport(FrozenModel):
    """Reviewed research report decisions with explicit safety boundaries."""

    schema_version: Literal[1] = 1
    batch_id: str = Field(min_length=1)
    report_id: str = Field(min_length=1)
    generated_at: datetime
    operational_authorization: ResearchOperationalAuthorization
    decisions: tuple[ResearchCandidateDecision, ...] = Field(min_length=1)

    @field_validator("decisions")
    @classmethod
    def candidate_decisions_must_be_unique(
        cls, decisions: tuple[ResearchCandidateDecision, ...]
    ) -> tuple[ResearchCandidateDecision, ...]:
        _require_unique(
            tuple(decision.candidate_id for decision in decisions),
            "decision candidate IDs",
        )
        return decisions


class ResearchTrialRecord(FrozenModel):
    """Trial ledger entry; failed and abandoned attempts remain first-class."""

    trial_id: str = Field(min_length=1)
    research_family_id: str = Field(min_length=1)
    candidate_id: str = Field(min_length=1)
    status: ResearchTrialStatus
    started_at: datetime
    completed_at: datetime | None = None
    message: str = ""
    artifact_paths: tuple[str, ...] = ()

    @model_validator(mode="after")
    def terminal_trials_must_have_completion_time(
        self,
    ) -> "ResearchTrialRecord":
        if (
            self.status != ResearchTrialStatus.PLANNED
            and self.completed_at is None
        ):
            raise ValueError("terminal research trials require completed_at")
        if (
            self.completed_at is not None
            and self.completed_at < self.started_at
        ):
            raise ValueError("completed_at must not precede started_at")
        return self


class StrategySimulationInput(FrozenModel):
    """Normalized existing-strategy output consumed by future simulators."""

    strategy_name: str = Field(min_length=1)
    symbol: str = Field(min_length=1)
    close: pd.Series
    signals: SignalFrame
    diagnostics: tuple[str, ...] = ()

    @field_validator("signals")
    @classmethod
    def signals_must_align_with_close(
        cls, signals: SignalFrame, info: ValidationInfo
    ) -> SignalFrame:
        close = info.data.get("close")
        if close is not None and not signals.entries.index.equals(close.index):
            raise ValueError("signals and close must share the same index")
        return signals


class ResearchArtifactDigest(FrozenModel):
    """Expected content digest for one immutable evaluation artifact."""

    relative_path: str = Field(min_length=1)
    sha256: str

    @field_validator("sha256")
    @classmethod
    def sha256_must_be_lowercase_hex(cls, value: str) -> str:
        return _validate_sha256(value)


class ResearchEvaluationManifest(FrozenModel):
    """Checksum manifest for immutable artifacts in one evaluation directory."""

    evaluation_id: str
    candidate_id: str
    immutable_artifacts: tuple[ResearchArtifactDigest, ...] = Field(
        min_length=1
    )

    @field_validator("evaluation_id")
    @classmethod
    def evaluation_id_must_be_sha256(cls, value: str) -> str:
        return _validate_sha256(value)

    @field_validator("immutable_artifacts")
    @classmethod
    def artifact_paths_must_be_unique(
        cls, artifacts: tuple[ResearchArtifactDigest, ...]
    ) -> tuple[ResearchArtifactDigest, ...]:
        _require_unique(
            tuple(artifact.relative_path for artifact in artifacts),
            "artifact paths",
        )
        return artifacts


class ResearchEvaluationArtifactPaths(FrozenModel):
    """Paths created for one immutable evaluation and append-only ledger."""

    evaluation_id: str
    output_dir: str
    candidate_json: str
    environment_json: str
    inputs_json: str
    splits_json: str
    scenarios_json: str
    manifest_json: str
    trials_jsonl: str

    @field_validator("evaluation_id")
    @classmethod
    def evaluation_id_must_be_sha256(cls, value: str) -> str:
        return _validate_sha256(value)


class ResearchBatchArtifactPaths(FrozenModel):
    """Paths created for one immutable research batch specification."""

    batch_id: str
    output_dir: str
    batch_json: str
    manifest_json: str


def _require_unique(values: tuple[str, ...], label: str) -> None:
    if len(values) != len(set(values)):
        raise ValueError(f"{label} must be unique")


def _validate_sha256(value: str) -> str:
    if len(value) != 64 or any(
        character not in "0123456789abcdef" for character in value
    ):
        raise ValueError("sha256 must be a 64-character lowercase hex digest")
    return value
