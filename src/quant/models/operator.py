"""Define reviewed operator-request contracts for semantic-target workflows."""

from typing import Literal

from pydantic import AwareDatetime, Field, field_validator

from quant.models.base import FrozenModel
from quant.models.execution import LiveAccountSnapshot
from quant.models.execution_lifecycle import ExecutionLifecyclePolicy
from quant.models.targets import ResearchRiskPolicy


class ActivatedDryRunOperatorRequest(FrozenModel):
    """Immutable reviewed request for one activated semantic-target dry-run."""

    schema_version: Literal[1] = 1
    request_id: str = Field(min_length=1)
    activation_evaluation_id: str = Field(min_length=1)
    orchestration_id: str = Field(min_length=1)
    authorization_path: str = Field(min_length=1)
    rehearsal_report_path: str = Field(min_length=1)
    activation_consumption_rehearsal_report_path: str = Field(min_length=1)
    contributor_set_path: str = Field(min_length=1)
    strategy_decision_paths: tuple[str, ...] = Field(min_length=1)
    strategy_evaluation_paths: tuple[str, ...] = Field(min_length=1)
    risk_policy: ResearchRiskPolicy
    portfolio_target_id: str = Field(min_length=1)
    portfolio_target_revision: int = Field(ge=1)
    risk_target_id: str = Field(min_length=1)
    risk_target_revision: int = Field(ge=1)
    account: LiveAccountSnapshot
    execution_policy: ExecutionLifecyclePolicy
    reference_price: float = Field(gt=0)
    evaluated_at: AwareDatetime
    evidence_refs: tuple[str, ...] = ()

    @field_validator(
        "request_id", "activation_evaluation_id", "orchestration_id"
    )
    @classmethod
    def identifiers_must_be_safe_path_components(cls, value: str) -> str:
        if value in {".", ".."} or "/" in value or "\\" in value:
            raise ValueError(
                "operator request IDs must be safe path components"
            )
        return value

    @field_validator("strategy_decision_paths", "strategy_evaluation_paths")
    @classmethod
    def artifact_paths_must_be_unique(
        cls, paths: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(set(paths)) != len(paths):
            raise ValueError("operator request artifact paths must be unique")
        return paths
