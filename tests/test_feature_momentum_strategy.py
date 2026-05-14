from typing import Any, cast

import pandas as pd
import pytest

from quant.models.features import FeatureData
from quant.strategies import FeatureMomentumConfig, FeatureMomentumStrategy


def test_feature_momentum_strategy_uses_feature_columns() -> None:
    features = FeatureData(symbol="AAPL", frame=_feature_frame())
    strategy = FeatureMomentumStrategy(
        FeatureMomentumConfig(fast_column="ma_fast", slow_column="ma_slow")
    )

    signals = strategy.generate_signals_from_features(features)

    assert signals.entries.dtype == bool
    assert signals.exits.dtype == bool
    assert signals.entries.index.equals(signals.exits.index)
    assert _true_dates(signals.entries) == [
        pd.Timestamp("2024-01-03"),
        pd.Timestamp("2024-01-06"),
    ]
    assert _true_dates(signals.exits) == [pd.Timestamp("2024-01-05")]


def test_feature_momentum_strategy_rejects_missing_columns() -> None:
    features = FeatureData(
        symbol="AAPL",
        frame=_feature_frame().drop(columns=["ma_fast"]),
    )
    strategy = FeatureMomentumStrategy(
        FeatureMomentumConfig(fast_column="ma_fast", slow_column="ma_slow")
    )

    with pytest.raises(ValueError, match="ma_fast"):
        strategy.generate_signals_from_features(features)


def _feature_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [
                timestamp.date()
                for timestamp in pd.date_range("2024-01-01", periods=6)
            ],
            "symbol": ["AAPL"] * 6,
            "close": [10.0, 11.0, 12.0, 11.0, 10.0, 12.0],
            # First row mimics rolling-feature warm-up; it should not emit a
            # signal until the strategy has a real above/below comparison.
            "ma_fast": [None, 9.0, 12.0, 13.0, 9.0, 12.0],
            "ma_slow": [None, 10.0, 10.0, 10.0, 10.0, 10.0],
        }
    )


def _true_dates(series: pd.Series) -> list[pd.Timestamp]:
    dates: list[pd.Timestamp] = []
    for index, value in series.items():
        if value:
            timestamp = pd.Timestamp(cast(Any, index))
            assert isinstance(timestamp, pd.Timestamp)
            dates.append(timestamp)
    return dates
