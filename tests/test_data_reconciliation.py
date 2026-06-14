"""Test data reconciliation behavior and safety invariants."""

import re
from pathlib import Path

from typer.testing import CliRunner

from quant.cli import app
from quant.data import reconcile_market_bars_csv

ANSI_PATTERN = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def test_reconcile_market_bars_passes_matching_data(tmp_path) -> None:
    left = _write_prices(tmp_path / "left.csv", close_values=[10.0, 11.0])
    right = _write_prices(tmp_path / "right.csv", close_values=[10.0, 11.0])

    report = reconcile_market_bars_csv(
        left_path=left,
        right_path=right,
        symbol="AAPL",
    )

    assert report.passed
    assert report.overlap_rows == 2
    assert report.close_differences == ()
    assert report.issue_count == 0


def test_reconcile_market_bars_fails_close_mismatch(tmp_path) -> None:
    left = _write_prices(tmp_path / "left.csv", close_values=[10.0, 12.0])
    right = _write_prices(tmp_path / "right.csv", close_values=[10.0, 11.0])

    report = reconcile_market_bars_csv(
        left_path=left,
        right_path=right,
        symbol="AAPL",
        close_tolerance_pct=0.001,
    )

    assert not report.passed
    assert len(report.close_differences) == 1
    assert report.close_differences[0].date == "2024-01-02"
    assert [issue.code for issue in report.issues] == ["close_mismatch"]


def test_reconcile_cli_writes_report_and_exits_on_mismatch(tmp_path) -> None:
    left = _write_prices(tmp_path / "left.csv", close_values=[10.0, 12.0])
    right = _write_prices(tmp_path / "right.csv", close_values=[10.0, 11.0])
    output_dir = tmp_path / "reconciliation"

    result = CliRunner().invoke(
        app,
        [
            "data",
            "reconcile",
            "--left",
            str(left),
            "--right",
            str(right),
            "--symbol",
            "AAPL",
            "--output-dir",
            str(output_dir),
        ],
    )
    output = strip_ansi(result.output)

    assert result.exit_code == 1
    assert "Status: failed" in output
    assert "close_mismatch" in output
    assert (output_dir / "AAPL.json").exists()


def _write_prices(
    path: Path,
    *,
    close_values: list[float],
) -> Path:
    rows = [
        "date,symbol,open,high,low,close,volume",
        f"2024-01-01,AAPL,10,11,9,{close_values[0]},100",
        f"2024-01-02,AAPL,11,12,10,{close_values[1]},110",
    ]
    path.write_text("\n".join(rows))
    return path


def strip_ansi(output: str) -> str:
    return ANSI_PATTERN.sub("", output)
