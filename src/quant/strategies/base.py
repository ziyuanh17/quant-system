"""
Base interfaces and protocols for quantitative trading strategies.
"""

from typing import Protocol

from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.signals import SignalFrame
from quant.models.targets import StrategyTargetFrame


class Strategy(Protocol):
    """
    Protocol defining the required interface for any trading strategy.

    This uses structural subtyping (duck typing). Concrete strategy classes
    do NOT need to explicitly inherit from this class. As long as they implement
    a `name` attribute and a `generate_signals` method with matching signatures,
    type checkers will consider them a valid `Strategy`.
    """

    name: str

    def generate_signals(self, prices: PriceData) -> SignalFrame:
        """
        Generate trading signals based on provided price data.

        Args:
            prices: Historical market data containing OHLCV prices, etc.

        Returns:
            A frame of generated trading signals (e.g., target positions or
            entries/exits).
        """
        ...


class FeatureStrategy(Protocol):
    """
    Protocol for strategies that consume precomputed feature artifacts.

    Keeping this separate from `Strategy` makes it obvious whether a backtest
    recomputes indicators from prices or consumes a reproducible feature file.
    """

    name: str

    def generate_signals_from_features(
        self, features: FeatureData
    ) -> SignalFrame: ...


class TargetStrategy(Protocol):
    """Price strategy that emits desired position targets directly."""

    name: str

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame: ...


class FeatureTargetStrategy(Protocol):
    """Feature strategy that emits desired position targets directly."""

    name: str

    def generate_targets_from_features(
        self, features: FeatureData
    ) -> StrategyTargetFrame: ...
