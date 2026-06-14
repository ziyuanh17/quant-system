"""Define domain models for shared immutable domain-model behavior."""

from pydantic import BaseModel, ConfigDict


class FrozenModel(BaseModel):
    """Base model for immutable domain records."""

    model_config = ConfigDict(
        frozen=True, extra="forbid", arbitrary_types_allowed=True
    )
