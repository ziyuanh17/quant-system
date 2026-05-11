"""yfinance market bar provider implementation."""

from typing import Any, cast

import pandas as pd

from quant.models.ingestion import DataModality, IngestRequest, RawDataset


class YFinanceMarketBarProvider:
    name = "yfinance"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        try:
            import yfinance as yf
        except ImportError as exc:
            raise RuntimeError(
                "yfinance is not installed. Run "
                '`python -m pip install -e ".[dev]"` and try again.'
            ) from exc

        records: list[dict[str, Any]] = []
        for symbol in request.symbols:
            frame = yf.download(
                symbol,
                start=request.start,
                end=request.end,
                auto_adjust=False,
                progress=False,
            )
            if frame is None:
                continue
            records.extend(_frame_to_records(frame, symbol))

        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=records,
        )


def _frame_to_records(frame: pd.DataFrame, symbol: str) -> list[dict[str, Any]]:
    if frame.empty:
        return []

    raw = _flatten_columns(frame).reset_index()
    raw["symbol"] = symbol
    return cast(list[dict[str, Any]], raw.to_dict(orient="records"))


def _flatten_columns(frame: pd.DataFrame) -> pd.DataFrame:
    flattened = frame.copy()
    flattened.columns = [
        _flatten_column(column) for column in flattened.columns.to_list()
    ]
    return flattened


def _flatten_column(column: Any) -> str:
    if isinstance(column, tuple):
        parts = [str(part) for part in column if str(part)]
        if parts:
            return parts[0]
    return str(column)
