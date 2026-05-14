from typing import cast

import pandas as pd
from pydantic import Field, field_validator

from quant.models.base import FrozenModel


class TechnicalFeatureConfig(FrozenModel):
    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)
    volatility_window: int = Field(default=20, ge=2)
    momentum_window: int = Field(default=20, ge=1)


class FeatureArtifactPaths(FrozenModel):
    features_path: str


class FeatureData(FrozenModel):
    """Typed wrapper for precomputed strategy features.

    A feature artifact is intentionally wider than market-bar data, but every
    backtest still needs the identity columns below to align signals to prices.
    """

    symbol: str
    frame: pd.DataFrame

    @field_validator("frame")
    @classmethod
    def frame_must_have_feature_identity_columns(
        cls, frame: pd.DataFrame
    ) -> pd.DataFrame:
        missing = [
            column
            for column in ("date", "symbol", "close")
            if column not in frame.columns
        ]
        if missing:
            raise ValueError(f"feature frame is missing columns: {missing}")
        if frame.empty:
            raise ValueError("feature frame must not be empty")
        return frame

    @property
    def close(self) -> pd.Series:
        close = cast(pd.Series, self.frame["close"]).copy()
        close.index = pd.to_datetime(self.frame["date"])
        close.name = self.symbol
        return cast(pd.Series, close.sort_index())
