"""Test data validation behavior and safety invariants."""

import pandas as pd

from quant.data.validation import validate_market_bars_csv
from quant.models.validation import ValidationReport


def test_validate_market_bars_csv_passes_clean_dataset(tmp_path) -> None:
    path = tmp_path / "AAPL.csv"
    _clean_frame().to_csv(path, index=False)

    report = validate_market_bars_csv(path, "AAPL", min_rows=2)

    assert report.passed is True
    assert report.rows == 2
    assert report.issue_count == 0


def test_validate_market_bars_csv_fails_missing_column(tmp_path) -> None:
    path = tmp_path / "AAPL.csv"
    frame = _clean_frame().drop(columns=["volume"])
    frame.to_csv(path, index=False)

    report = validate_market_bars_csv(path, "AAPL")

    assert report.passed is False
    assert _issue_codes(report) == {"missing_column"}


def test_validate_market_bars_csv_fails_bad_rows(tmp_path) -> None:
    path = tmp_path / "AAPL.csv"
    frame = pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-02", "2024-01-01"],
            "symbol": ["AAPL", "MSFT", "AAPL"],
            "open": [100.0, 100.0, -1.0],
            "high": [99.0, 103.0, 101.0],
            "low": [100.0, 95.0, 90.0],
            "close": [101.0, 102.0, 95.0],
            "volume": [1000, -5, 500],
        }
    )
    frame.to_csv(path, index=False)

    report = validate_market_bars_csv(path, "AAPL", min_rows=5)

    assert report.passed is False
    assert {
        "duplicate_date",
        "invalid_ohlc",
        "negative_volume",
        "non_positive_price",
        "symbol_mismatch",
        "too_few_rows",
        "unsorted_dates",
    }.issubset(_issue_codes(report))


def _clean_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "symbol": ["AAPL", "AAPL"],
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [99.0, 100.0],
            "close": [104.0, 105.0],
            "volume": [1000, 1200],
        }
    )


def _issue_codes(report: ValidationReport) -> set[str]:
    return {issue.code for issue in report.issues}
