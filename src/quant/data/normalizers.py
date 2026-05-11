from typing import Any

import pandas as pd

from quant.models.ingestion import RawDataset
from quant.models.market import REQUIRED_PRICE_COLUMNS, PriceData

YFINANCE_COLUMN_MAP = {
    "Date": "date",
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adjusted_close",
    "Volume": "volume",
}


def normalize_market_bars(raw: RawDataset, symbol: str) -> PriceData:
    frame = pd.DataFrame(raw.records)
    if frame.empty:
        raise ValueError(f"provider returned no records for symbol {symbol}")

    normalized = frame.rename(columns=YFINANCE_COLUMN_MAP)
    normalized = normalized.loc[normalized["symbol"] == symbol].copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.date
    normalized["provider"] = raw.provider

    required = list(REQUIRED_PRICE_COLUMNS)
    optional = ["adjusted_close", "provider"]
    columns = [column for column in required + optional if column in normalized]
    normalized = normalized[columns].sort_values("date").reset_index(drop=True)

    return PriceData(symbol=symbol, frame=normalized)


def raw_records_for_csv(raw: RawDataset, symbol: str) -> pd.DataFrame:
    frame = pd.DataFrame(raw.records)
    if "symbol" in frame.columns:
        frame = frame.loc[frame["symbol"] == symbol].copy()
    return _stringify_nested_columns(frame)


def _stringify_nested_columns(frame: pd.DataFrame) -> pd.DataFrame:
    for column in frame.columns:
        frame[column] = frame[column].map(_csv_safe_value)
    return frame


def _csv_safe_value(value: Any) -> Any:
    if isinstance(value, (dict, list, tuple)):
        return str(value)
    return value
