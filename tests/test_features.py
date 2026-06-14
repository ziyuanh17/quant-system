"""Test features behavior and safety invariants."""

import pandas as pd
import pytest

from quant.features import (
    build_technical_features,
    load_feature_csv,
    write_feature_artifact,
)
from quant.models.features import TechnicalFeatureConfig
from quant.models.market import PriceData


def test_build_technical_features_adds_expected_columns() -> None:
    prices = PriceData(symbol="AAPL", frame=_price_frame())

    features = build_technical_features(
        prices,
        TechnicalFeatureConfig(
            fast_window=2,
            slow_window=3,
            volatility_window=2,
            momentum_window=2,
        ),
    )

    assert list(features.columns) == [
        "date",
        "symbol",
        "close",
        "daily_return",
        "log_return",
        "ma_2",
        "ma_3",
        "volatility_2",
        "momentum_2",
        "drawdown",
    ]
    assert features.loc[1, "daily_return"] == pytest.approx(0.1)
    assert features.loc[2, "ma_2"] == 11.5
    assert features.loc[3, "momentum_2"] == pytest.approx(0.2)


def test_write_feature_artifact_writes_csv(tmp_path) -> None:
    features = build_technical_features(
        PriceData(symbol="AAPL", frame=_price_frame()),
        TechnicalFeatureConfig(fast_window=2, slow_window=3),
    )

    artifact = write_feature_artifact(features, tmp_path, "AAPL")

    assert artifact.features_path == str(tmp_path / "AAPL.csv")
    assert (tmp_path / "AAPL.csv").exists()


def test_load_feature_csv_filters_symbol_and_preserves_close_series(
    tmp_path,
) -> None:
    features = pd.DataFrame(
        {
            "date": [
                "2024-01-02",
                "2024-01-01",
                "2024-01-01",
            ],
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "close": [11.0, 99.0, 10.0],
            "ma_2": [10.5, 99.0, None],
            "ma_3": [None, 99.0, None],
        }
    )
    path = tmp_path / "features.csv"
    features.to_csv(path, index=False)

    loaded = load_feature_csv(path, "AAPL")

    assert loaded.symbol == "AAPL"
    assert loaded.frame["symbol"].tolist() == ["AAPL", "AAPL"]
    assert loaded.close.index.tolist() == [
        pd.Timestamp("2024-01-01"),
        pd.Timestamp("2024-01-02"),
    ]
    assert loaded.close.tolist() == [10.0, 11.0]


def _price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [
                timestamp.date()
                for timestamp in pd.date_range("2024-01-01", periods=4)
            ],
            "symbol": ["AAPL"] * 4,
            "open": [10.0, 11.0, 12.0, 12.0],
            "high": [10.5, 11.5, 12.5, 12.5],
            "low": [9.5, 10.5, 11.5, 11.5],
            "close": [10.0, 11.0, 12.0, 13.2],
            "volume": [100, 110, 120, 130],
        }
    )
