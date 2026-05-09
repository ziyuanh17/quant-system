from datetime import date
from typing import cast

import pandas as pd
from pydantic import Field, field_validator

from quant.models.base import FrozenModel

REQUIRED_PRICE_COLUMNS = (
    "date",
    "symbol",
    "open",
    "high",
    "low",
    "close",
    "volume",
)


class Bar(FrozenModel):
    symbol: str
    date: date
    open: float = Field(gt=0)
    high: float = Field(gt=0)
    low: float = Field(gt=0)
    close: float = Field(gt=0)
    volume: int = Field(ge=0)


class PriceData(FrozenModel):
    symbol: str
    frame: pd.DataFrame

    @field_validator("frame")
    @classmethod
    def frame_must_have_price_columns(cls, frame: pd.DataFrame) -> pd.DataFrame:
        missing = [
            column
            for column in REQUIRED_PRICE_COLUMNS
            if column not in frame.columns
        ]
        if missing:
            raise ValueError(
                f"price frame is missing required columns: {missing}"
            )
        if frame.empty:
            raise ValueError("price frame must not be empty")
        return frame

    @property
    def close(self) -> pd.Series:
        close = cast(pd.Series, self.frame["close"]).copy()
        close.index = pd.to_datetime(self.frame["date"])
        close.name = self.symbol
        return cast(pd.Series, close.sort_index())
