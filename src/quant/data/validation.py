"""Validate canonical market-bar datasets and report issues."""

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pandas as pd

from quant.models.market import REQUIRED_PRICE_COLUMNS
from quant.models.validation import (
    ValidationIssue,
    ValidationReport,
    ValidationSeverity,
)


def validate_market_bars_csv(
    path: Path,
    symbol: str,
    *,
    min_rows: int = 1,
) -> ValidationReport:
    frame = pd.read_csv(path)
    issues = list(_validate_market_bar_frame(frame, symbol, min_rows=min_rows))

    return ValidationReport(
        dataset=str(path),
        symbol=symbol,
        rows=len(frame),
        passed=not any(
            issue.severity == ValidationSeverity.ERROR for issue in issues
        ),
        issues=tuple(issues),
    )


def _validate_market_bar_frame(
    frame: pd.DataFrame,
    symbol: str,
    *,
    min_rows: int,
) -> Iterable[ValidationIssue]:
    missing_columns = [
        column
        for column in REQUIRED_PRICE_COLUMNS
        if column not in frame.columns
    ]
    for column in missing_columns:
        yield _issue(
            "missing_column",
            f"required column is missing: {column}",
            field=column,
        )

    if missing_columns:
        return

    if len(frame) < min_rows:
        yield _issue(
            "too_few_rows",
            f"dataset has {len(frame)} rows, expected at least {min_rows}",
        )

    yield from _validate_symbol(frame, symbol)
    yield from _validate_required_values(frame)
    yield from _validate_dates(frame)
    yield from _validate_prices(frame)
    yield from _validate_volume(frame)


def _validate_symbol(
    frame: pd.DataFrame, symbol: str
) -> Iterable[ValidationIssue]:
    mismatches = frame.index[frame["symbol"] != symbol].tolist()
    for index in mismatches:
        yield _issue(
            "symbol_mismatch",
            f"row symbol does not match expected symbol {symbol}",
            row=int(index),
            field="symbol",
        )


def _validate_required_values(frame: pd.DataFrame) -> Iterable[ValidationIssue]:
    for column in REQUIRED_PRICE_COLUMNS:
        null_rows = frame.index[frame[column].isna()].tolist()
        for index in null_rows:
            yield _issue(
                "missing_value",
                f"missing value in column {column}",
                row=int(index),
                field=column,
            )


def _validate_dates(frame: pd.DataFrame) -> Iterable[ValidationIssue]:
    dates = cast(pd.Series, pd.to_datetime(frame["date"], errors="coerce"))

    for index in frame.index[dates.isna()].tolist():
        yield _issue(
            "invalid_date",
            "date could not be parsed",
            row=int(index),
            field="date",
        )

    duplicate_rows = frame.index[dates.duplicated(keep=False)].tolist()
    for index in duplicate_rows:
        yield _issue(
            "duplicate_date",
            "date appears more than once",
            row=int(index),
            field="date",
        )

    valid_dates = dates.dropna()
    if not valid_dates.is_monotonic_increasing:
        yield _issue(
            "unsorted_dates",
            "dates are not sorted ascending",
            field="date",
        )


def _validate_prices(frame: pd.DataFrame) -> Iterable[ValidationIssue]:
    numeric = _numeric_columns(frame, ["open", "high", "low", "close"])

    for column in ["open", "high", "low", "close"]:
        invalid_rows = frame.index[numeric[column].isna()].tolist()
        for index in invalid_rows:
            yield _issue(
                "invalid_price",
                f"{column} is not numeric",
                row=int(index),
                field=column,
            )

        non_positive_rows = frame.index[numeric[column] <= 0].tolist()
        for index in non_positive_rows:
            yield _issue(
                "non_positive_price",
                f"{column} must be positive",
                row=int(index),
                field=column,
            )

    yield from _validate_ohlc_relationships(numeric)


def _validate_ohlc_relationships(
    numeric: pd.DataFrame,
) -> Iterable[ValidationIssue]:
    for index in numeric.index[numeric["high"] < numeric["low"]].tolist():
        yield _issue(
            "invalid_ohlc",
            "high is below low",
            row=int(index),
            field="high",
        )

    for column in ["open", "close"]:
        high_breaks = numeric.index[numeric["high"] < numeric[column]].tolist()
        for index in high_breaks:
            yield _issue(
                "invalid_ohlc",
                f"high is below {column}",
                row=int(index),
                field="high",
            )

        low_breaks = numeric.index[numeric["low"] > numeric[column]].tolist()
        for index in low_breaks:
            yield _issue(
                "invalid_ohlc",
                f"low is above {column}",
                row=int(index),
                field="low",
            )


def _validate_volume(frame: pd.DataFrame) -> Iterable[ValidationIssue]:
    volume = cast(pd.Series, pd.to_numeric(frame["volume"], errors="coerce"))

    for index in frame.index[volume.isna()].tolist():
        yield _issue(
            "invalid_volume",
            "volume is not numeric",
            row=int(index),
            field="volume",
        )

    for index in frame.index[volume < 0].tolist():
        yield _issue(
            "negative_volume",
            "volume must be non-negative",
            row=int(index),
            field="volume",
        )


def _numeric_columns(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    numeric = pd.DataFrame(index=frame.index)
    for column in columns:
        numeric[column] = pd.to_numeric(frame[column], errors="coerce")
    return numeric


def _issue(
    code: str,
    message: str,
    *,
    row: int | None = None,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=ValidationSeverity.ERROR,
        message=message,
        row=row,
        field=field,
    )
