from typing import cast

import numpy as np
import pandas as pd

from quant.models.features import TechnicalFeatureConfig
from quant.models.market import PriceData


def build_technical_features(
    prices: PriceData,
    config: TechnicalFeatureConfig | None = None,
) -> pd.DataFrame:
    """Build deterministic technical features from validated market bars."""
    config = config or TechnicalFeatureConfig()
    frame = prices.frame.copy()

    # Keep feature math numeric even when CSV loading widens dtypes to object.
    close = cast(pd.Series, pd.to_numeric(frame["close"], errors="coerce"))

    # Preserve identity columns so feature artifacts remain joinable to prices.
    features = pd.DataFrame(
        {
            "date": frame["date"],
            "symbol": frame["symbol"],
            "close": close,
        }
    )

    # Returns are intentionally simple first-pass features; later versions can
    # add adjusted-close policy and benchmark-relative variants.
    features["daily_return"] = close.pct_change()
    features["log_return"] = np.log(close / close.shift(1))

    # Rolling features leave warm-up rows as NaN, making lookback availability
    # explicit instead of silently forward-filling unavailable history.
    features[f"ma_{config.fast_window}"] = close.rolling(
        config.fast_window
    ).mean()
    features[f"ma_{config.slow_window}"] = close.rolling(
        config.slow_window
    ).mean()
    features[f"volatility_{config.volatility_window}"] = (
        features["daily_return"].rolling(config.volatility_window).std()
    )
    features[f"momentum_{config.momentum_window}"] = close.pct_change(
        config.momentum_window
    )

    # Drawdown is measured from each point's prior cumulative high.
    features["drawdown"] = close / close.cummax() - 1
    return features
