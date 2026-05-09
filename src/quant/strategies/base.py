"""
Base interfaces and protocols for quantitative trading strategies.
"""

from typing import Protocol

from quant.models.market import PriceData
from quant.models.signals import SignalFrame


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
