"""Expose the public quant.strategies package API."""

from quant.strategies.base import FeatureTargetStrategy, TargetStrategy
from quant.strategies.feature_momentum import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
)
from quant.strategies.momentum import MomentumConfig, MomentumStrategy
from quant.strategies.research_targets import (
    DeclaredNotionalTrendConfig,
    DeclaredNotionalTrendStrategy,
    MeanReversionCounterweightConfig,
    MeanReversionCounterweightStrategy,
    TargetNativeTrendConfig,
    TargetNativeTrendStrategy,
    VolatilityAdjustedTrendConfig,
    VolatilityAdjustedTrendStrategy,
)

__all__ = [
    "DeclaredNotionalTrendConfig",
    "DeclaredNotionalTrendStrategy",
    "FeatureMomentumConfig",
    "FeatureMomentumStrategy",
    "FeatureTargetStrategy",
    "MeanReversionCounterweightConfig",
    "MeanReversionCounterweightStrategy",
    "MomentumConfig",
    "MomentumStrategy",
    "TargetStrategy",
    "TargetNativeTrendConfig",
    "TargetNativeTrendStrategy",
    "VolatilityAdjustedTrendConfig",
    "VolatilityAdjustedTrendStrategy",
]
