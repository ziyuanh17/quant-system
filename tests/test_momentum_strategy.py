import pandas as pd

from quant.models.market import PriceData
from quant.strategies.momentum import MomentumConfig, MomentumStrategy


def test_momentum_strategy_returns_aligned_boolean_signals() -> None:
    frame = pd.DataFrame(
        {
            "date": [
                timestamp.date()
                for timestamp in pd.date_range("2024-01-01", periods=8)
            ],
            "symbol": ["AAPL"] * 8,
            "open": [10, 10, 10, 10, 10, 10, 10, 10],
            "high": [11, 11, 11, 11, 11, 11, 11, 11],
            "low": [9, 9, 9, 9, 9, 9, 9, 9],
            "close": [10, 11, 12, 13, 14, 13, 12, 11],
            "volume": [100] * 8,
        }
    )
    prices = PriceData(symbol="AAPL", frame=frame)
    strategy = MomentumStrategy(MomentumConfig(fast_window=2, slow_window=3))

    signals = strategy.generate_signals(prices)

    assert signals.entries.dtype == bool
    assert signals.exits.dtype == bool
    assert signals.entries.index.equals(signals.exits.index)
