"""Implement the legacy price-momentum strategy."""

import pandas as pd
from pydantic import Field

from quant.models.base import FrozenModel
from quant.models.market import PriceData
from quant.models.signals import SignalFrame


class MomentumConfig(FrozenModel):
    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)


class MomentumStrategy:
    """
    A simple trend-following strategy that generates buy signals when the
    fast moving average crosses above the slow moving average, and sell
    signals when it crosses below.

    This class implements the `Strategy` protocol (though it does not inherit
    from it), meaning it can be used wherever a `Strategy` is expected.
    """

    name: str = "momentum"

    def __init__(self, config: MomentumConfig | None = None) -> None:
        self.config = config or MomentumConfig()
        if self.config.fast_window >= self.config.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")

    def generate_signals(self, prices: PriceData) -> SignalFrame:
        """
        Generate signals based on moving average crossover.

        Args:
            prices: Price data with OHLCV values and datetime index.

        Returns:
            SignalFrame containing boolean arrays for entries and exits.
        """
        close = prices.close
        fast_average = close.rolling(self.config.fast_window).mean()
        slow_average = close.rolling(self.config.slow_window).mean()

        above = pd.Series(
            fast_average > slow_average, index=close.index, dtype=bool
        )
        previous_above = above.shift(1, fill_value=False)

        entries = (above & ~previous_above).fillna(False)
        exits = (~above & previous_above).fillna(False)

        return SignalFrame(
            entries=pd.Series(entries, index=close.index, dtype=bool),
            exits=pd.Series(exits, index=close.index, dtype=bool),
        )
