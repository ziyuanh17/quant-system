"""Define domain models for legacy strategy signal frames."""

import pandas as pd
from pydantic import ValidationInfo, field_validator

from quant.models.base import FrozenModel


class SignalFrame(FrozenModel):
    entries: pd.Series
    exits: pd.Series

    @field_validator("entries", "exits")
    @classmethod
    def signals_must_be_boolean_series(cls, series: pd.Series) -> pd.Series:
        if series.dtype != bool:
            raise ValueError("signal series must be boolean")
        return series

    @field_validator("exits")
    @classmethod
    def exits_must_align_with_entries(
        cls, exits: pd.Series, info: ValidationInfo
    ) -> pd.Series:
        entries = info.data.get("entries")
        if entries is not None and not exits.index.equals(entries.index):
            raise ValueError("entries and exits must share the same index")
        return exits
