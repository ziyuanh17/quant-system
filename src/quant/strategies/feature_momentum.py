from typing import cast

import pandas as pd

from quant.models.base import FrozenModel
from quant.models.features import FeatureData
from quant.models.signals import SignalFrame


class FeatureMomentumConfig(FrozenModel):
    fast_column: str = "ma_5"
    slow_column: str = "ma_20"


class FeatureMomentumStrategy:
    """
    Momentum strategy that consumes feature columns instead of recomputing them.

    This is the bridge from "strategy owns feature math" to "strategy consumes
    feature artifacts", which makes backtests easier to reproduce and audit.
    """

    name = "feature-momentum"

    def __init__(self, config: FeatureMomentumConfig | None = None) -> None:
        self.config = config or FeatureMomentumConfig()

    def generate_signals_from_features(
        self, features: FeatureData
    ) -> SignalFrame:
        missing = [
            column
            for column in (self.config.fast_column, self.config.slow_column)
            if column not in features.frame.columns
        ]
        if missing:
            raise ValueError(f"feature frame is missing columns: {missing}")

        frame = features.frame.copy()
        dates = cast(pd.Series, pd.to_datetime(frame["date"]))
        fast = cast(
            pd.Series,
            pd.to_numeric(frame[self.config.fast_column], errors="coerce"),
        )
        slow = cast(
            pd.Series,
            pd.to_numeric(frame[self.config.slow_column], errors="coerce"),
        )

        # Reindex by assignment instead of constructing from another Series;
        # otherwise pandas aligns on labels and can silently create all-NaN
        # data.
        fast.index = dates
        slow.index = dates

        # NaN warm-up rows are expected for rolling features; treating them as
        # not-above prevents signals before the lookback window is available.
        above = pd.Series(fast > slow, index=dates, dtype=bool).fillna(False)
        previous_above = above.shift(1, fill_value=False)

        entries = (above & ~previous_above).fillna(False)
        exits = (~above & previous_above).fillna(False)

        return SignalFrame(
            entries=pd.Series(entries, index=dates, dtype=bool),
            exits=pd.Series(exits, index=dates, dtype=bool),
        )
