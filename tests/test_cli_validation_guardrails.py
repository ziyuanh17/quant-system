from typer.testing import CliRunner

from quant.cli import app


def test_backtest_fails_invalid_data_before_strategy_runs(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "\n".join(
            [
                "date,symbol,open,high,low,close,volume",
                "2024-01-02,AAPL,100,99,100,101,1000",
            ]
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "--data",
            str(path),
            "--symbol",
            "AAPL",
        ],
    )

    assert result.exit_code == 1
    assert "Status: failed" in result.output
    assert "invalid_ohlc" in result.output
    assert "Strategy:" not in result.output


def test_backtest_skip_validation_continues_on_invalid_data(tmp_path) -> None:
    path = tmp_path / "bad.csv"
    path.write_text(
        "\n".join(
            [
                "date,symbol,open,high,low,close,volume",
                "2024-01-02,AAPL,100,99,100,101,1000",
            ]
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "--data",
            str(path),
            "--symbol",
            "AAPL",
            "--skip-validation",
            "--output-dir",
            str(tmp_path / "results"),
        ],
    )

    assert result.exit_code == 0
    assert "Strategy: momentum" in result.output
