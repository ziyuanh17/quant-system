"""Load validated market price data from CSV files."""

from pathlib import Path

import pandas as pd

from quant.models.market import PriceData


def load_price_csv(path: Path, symbol: str) -> PriceData:
    frame = pd.read_csv(path)
    frame = frame.loc[frame["symbol"] == symbol].copy()
    # pyrefly: ignore [missing-attribute]
    frame["date"] = pd.to_datetime(frame["date"]).dt.date
    # pyrefly: ignore [no-matching-overload]
    frame = frame.sort_values("date").reset_index(drop=True)
    return PriceData(symbol=symbol, frame=frame)
