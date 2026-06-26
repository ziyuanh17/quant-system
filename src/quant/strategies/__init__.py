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
    HysteresisNotionalTrendConfig,
    HysteresisNotionalTrendStrategy,
    MeanReversionCounterweightConfig,
    MeanReversionCounterweightStrategy,
    RebalanceBandNotionalTrendConfig,
    RebalanceBandNotionalTrendStrategy,
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
    "HysteresisNotionalTrendConfig",
    "HysteresisNotionalTrendStrategy",
    "MeanReversionCounterweightConfig",
    "MeanReversionCounterweightStrategy",
    "MomentumConfig",
    "MomentumStrategy",
    "RebalanceBandNotionalTrendConfig",
    "RebalanceBandNotionalTrendStrategy",
    "TargetStrategy",
    "TargetNativeTrendConfig",
    "TargetNativeTrendStrategy",
    "VolatilityAdjustedTrendConfig",
    "VolatilityAdjustedTrendStrategy",
]
