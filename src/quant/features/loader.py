from pathlib import Path

import pandas as pd

from quant.models.features import FeatureData


def load_feature_csv(path: Path, symbol: str) -> FeatureData:
    frame = pd.read_csv(path)
    frame = frame.loc[frame["symbol"] == symbol].copy()
    # Feature artifacts preserve one row per market bar; date sorting keeps
    # signal indices aligned with VectorBT's close-price input.
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    frame = frame.sort_values("date").reset_index(drop=True)
    return FeatureData(symbol=symbol, frame=frame)
