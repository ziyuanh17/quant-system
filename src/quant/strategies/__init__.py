"""Expose the public quant.strategies package API."""

from quant.strategies.base import FeatureTargetStrategy, TargetStrategy
from quant.strategies.feature_momentum import (
    FeatureMomentumConfig,
    FeatureMomentumStrategy,
)
from quant.strategies.momentum import MomentumConfig, MomentumStrategy

__all__ = [
    "FeatureMomentumConfig",
    "FeatureMomentumStrategy",
    "FeatureTargetStrategy",
    "MomentumConfig",
    "MomentumStrategy",
    "TargetStrategy",
]
