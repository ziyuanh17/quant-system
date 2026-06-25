"""Test research-only target strategy semantics."""

from decimal import Decimal

import pandas as pd

from quant.models.market import PriceData
from quant.strategies import (
    MeanReversionCounterweightConfig,
    MeanReversionCounterweightStrategy,
    TargetNativeTrendConfig,
    TargetNativeTrendStrategy,
    VolatilityAdjustedTrendConfig,
    VolatilityAdjustedTrendStrategy,
)


def test_target_native_trend_emits_long_flat_short_targets() -> None:
    strategy = TargetNativeTrendStrategy(
        TargetNativeTrendConfig(fast_window=2, slow_window=3)
    )

    frame = strategy.generate_targets(
        _prices([10, 11, 12, 11, 10, 9, 10, 11, 12])
    )

    values = set(frame.targets.tolist())
    assert Decimal("0") in values
    assert Decimal("1") in values
    assert Decimal("-1") in values


def test_volatility_adjusted_trend_emits_fractional_research_targets() -> None:
    strategy = VolatilityAdjustedTrendStrategy(
        VolatilityAdjustedTrendConfig(
            fast_window=2,
            slow_window=3,
            volatility_window=3,
            min_target_shares=Decimal("0.25"),
            max_target_shares=Decimal("1.0"),
        )
    )

    frame = strategy.generate_targets(
        _prices([10, 11, 12, 13, 15, 16, 14, 13, 12, 11, 10, 12])
    )

    nonzero = [value for value in frame.targets.tolist() if value != 0]
    assert nonzero
    assert all(abs(value) <= Decimal("1.0") for value in nonzero)
    assert any(value != value.to_integral_value() for value in nonzero)


def test_mean_reversion_counterweight_carries_until_exit_band() -> None:
    strategy = MeanReversionCounterweightStrategy(
        MeanReversionCounterweightConfig(
            lookback_window=3,
            entry_zscore=Decimal("1.0"),
            exit_zscore=Decimal("0.25"),
        )
    )

    frame = strategy.generate_targets(
        _prices([10, 10, 10, 13, 13, 10, 7, 7, 10])
    )

    values = frame.targets.tolist()
    assert Decimal("-1") in values
    assert Decimal("1") in values
    assert Decimal("0") in values


def _prices(close: list[float]) -> PriceData:
    dates = pd.date_range("2024-01-01", periods=len(close))
    return PriceData(
        symbol="AAPL",
        frame=pd.DataFrame(
            {
                "date": [timestamp.date() for timestamp in dates],
                "symbol": ["AAPL"] * len(close),
                "open": close,
                "high": [value + 1 for value in close],
                "low": [value - 1 for value in close],
                "close": close,
                "volume": [1000] * len(close),
            }
        ),
    )
