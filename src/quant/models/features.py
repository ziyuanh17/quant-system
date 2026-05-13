from pydantic import Field

from quant.models.base import FrozenModel


class TechnicalFeatureConfig(FrozenModel):
    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)
    volatility_window: int = Field(default=20, ge=2)
    momentum_window: int = Field(default=20, ge=1)


class FeatureArtifactPaths(FrozenModel):
    features_path: str
