"""Compare normalized market data from independent providers."""

from collections.abc import Iterable
from pathlib import Path
from typing import cast

import pandas as pd

from quant.models.market import REQUIRED_PRICE_COLUMNS
from quant.models.reconciliation import (
    ProviderReconciliationReport,
    ReconciliationDifference,
)
from quant.models.validation import (
    ValidationIssue,
    ValidationSeverity,
)


def reconcile_market_bars_csv(
    *,
    left_path: Path,
    right_path: Path,
    symbol: str,
    close_tolerance_pct: float = 0.001,
    volume_tolerance_pct: float = 0.05,
) -> ProviderReconciliationReport:
    """Compare two normalized market-bar CSVs for the same symbol.

    The comparison intentionally happens after normalization. Provider-specific
    raw quirks should be handled upstream; this report asks whether two
    datasets now tell the same story for simulation and feature generation.
    """

    left_frame, left_issues = _load_symbol_frame(left_path, symbol, "left")
    right_frame, right_issues = _load_symbol_frame(right_path, symbol, "right")
    issues = [*left_issues, *right_issues]

    if left_frame.empty or right_frame.empty:
        return ProviderReconciliationReport(
            left_dataset=str(left_path),
            right_dataset=str(right_path),
            symbol=symbol,
            left_rows=len(left_frame),
            right_rows=len(right_frame),
            overlap_rows=0,
            left_only_dates=(),
            right_only_dates=(),
            close_differences=(),
            volume_differences=(),
            issues=tuple(issues),
        )

    left_by_date = left_frame.set_index("date", drop=False)
    right_by_date = right_frame.set_index("date", drop=False)
    left_dates = set(cast(Iterable[str], left_by_date.index))
    right_dates = set(cast(Iterable[str], right_by_date.index))
    left_only_dates = tuple(sorted(left_dates - right_dates))
    right_only_dates = tuple(sorted(right_dates - left_dates))
    overlap_dates = tuple(sorted(left_dates & right_dates))

    issues.extend(
        _coverage_issues(
            left_only_dates=left_only_dates,
            right_only_dates=right_only_dates,
        )
    )
    close_differences = tuple(
        _numeric_differences(
            left_by_date,
            right_by_date,
            overlap_dates,
            field="close",
            tolerance_pct=close_tolerance_pct,
        )
    )
    volume_differences = tuple(
        _numeric_differences(
            left_by_date,
            right_by_date,
            overlap_dates,
            field="volume",
            tolerance_pct=volume_tolerance_pct,
        )
    )

    issues.extend(
        _difference_issues(
            close_differences,
            code="close_mismatch",
            severity=ValidationSeverity.ERROR,
        )
    )
    issues.extend(
        _difference_issues(
            volume_differences,
            code="volume_mismatch",
            severity=ValidationSeverity.WARNING,
        )
    )

    return ProviderReconciliationReport(
        left_dataset=str(left_path),
        right_dataset=str(right_path),
        symbol=symbol,
        left_rows=len(left_frame),
        right_rows=len(right_frame),
        overlap_rows=len(overlap_dates),
        left_only_dates=left_only_dates,
        right_only_dates=right_only_dates,
        close_differences=close_differences,
        volume_differences=volume_differences,
        issues=tuple(issues),
    )


def write_reconciliation_report(
    report: ProviderReconciliationReport,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(report.model_dump_json(indent=2) + "\n")
    return path


def _load_symbol_frame(
    path: Path,
    symbol: str,
    side: str,
) -> tuple[pd.DataFrame, list[ValidationIssue]]:
    frame = pd.read_csv(path)
    issues = _schema_issues(frame, side)
    if issues:
        return pd.DataFrame(), issues

    symbol_frame = frame.loc[frame["symbol"] == symbol].copy()
    if symbol_frame.empty:
        issues.append(
            _issue(
                "missing_symbol",
                f"{side} dataset has no rows for symbol {symbol}",
                severity=ValidationSeverity.ERROR,
                field="symbol",
            )
        )
        return symbol_frame, issues

    dates = cast(pd.Series, pd.to_datetime(symbol_frame["date"]))
    symbol_frame["date"] = dates.dt.strftime("%Y-%m-%d")

    duplicate_dates = symbol_frame["date"].duplicated(keep=False)
    for date_value in symbol_frame.loc[duplicate_dates, "date"].tolist():
        issues.append(
            _issue(
                "duplicate_date",
                f"{side} dataset has duplicate date {date_value}",
                severity=ValidationSeverity.ERROR,
                date=str(date_value),
                field="date",
            )
        )

    return symbol_frame.sort_values("date").reset_index(drop=True), issues


def _schema_issues(
    frame: pd.DataFrame, side: str
) -> list[ValidationIssue]:
    return [
        _issue(
            "missing_column",
            f"{side} dataset is missing required column {column}",
            severity=ValidationSeverity.ERROR,
            field=column,
        )
        for column in REQUIRED_PRICE_COLUMNS
        if column not in frame.columns
    ]


def _coverage_issues(
    *,
    left_only_dates: tuple[str, ...],
    right_only_dates: tuple[str, ...],
) -> Iterable[ValidationIssue]:
    for date_value in left_only_dates:
        yield _issue(
            "left_only_date",
            f"date exists only in left dataset: {date_value}",
            severity=ValidationSeverity.WARNING,
            date=date_value,
            field="date",
        )
    for date_value in right_only_dates:
        yield _issue(
            "right_only_date",
            f"date exists only in right dataset: {date_value}",
            severity=ValidationSeverity.WARNING,
            date=date_value,
            field="date",
        )


def _numeric_differences(
    left_by_date: pd.DataFrame,
    right_by_date: pd.DataFrame,
    dates: tuple[str, ...],
    *,
    field: str,
    tolerance_pct: float,
) -> Iterable[ReconciliationDifference]:
    for date_value in dates:
        left_value = float(left_by_date.loc[date_value, field])
        right_value = float(right_by_date.loc[date_value, field])
        absolute_difference = abs(left_value - right_value)
        relative_difference = _relative_difference(
            absolute_difference, right_value
        )
        if relative_difference is None:
            exceeds_tolerance = absolute_difference > 0
        else:
            exceeds_tolerance = relative_difference > tolerance_pct

        if exceeds_tolerance:
            yield ReconciliationDifference(
                date=date_value,
                field=field,
                left_value=left_value,
                right_value=right_value,
                absolute_difference=absolute_difference,
                relative_difference=relative_difference,
            )


def _difference_issues(
    differences: tuple[ReconciliationDifference, ...],
    *,
    code: str,
    severity: ValidationSeverity,
) -> Iterable[ValidationIssue]:
    for difference in differences:
        yield _issue(
            code,
            (
                f"{difference.field} differs on {difference.date}: "
                f"left={difference.left_value}, "
                f"right={difference.right_value}"
            ),
            severity=severity,
            date=difference.date,
            field=difference.field,
        )


def _relative_difference(
    absolute_difference: float, denominator: float
) -> float | None:
    if denominator == 0:
        return None
    return absolute_difference / abs(denominator)


def _issue(
    code: str,
    message: str,
    *,
    severity: ValidationSeverity,
    date: str | None = None,
    field: str | None = None,
) -> ValidationIssue:
    return ValidationIssue(
        code=code,
        severity=severity,
        message=message,
        row=None,
        field=f"{field}@{date}" if date is not None else field,
    )
