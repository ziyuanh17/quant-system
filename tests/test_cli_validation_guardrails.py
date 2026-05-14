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


def test_feature_momentum_backtest_uses_feature_artifact(tmp_path) -> None:
    path = tmp_path / "features.csv"
    path.write_text(
        "\n".join(
            [
                "date,symbol,close,ma_fast,ma_slow",
                "2024-01-01,AAPL,10,,",
                "2024-01-02,AAPL,11,9,10",
                "2024-01-03,AAPL,12,12,10",
                "2024-01-04,AAPL,11,13,10",
                "2024-01-05,AAPL,10,9,10",
                "2024-01-06,AAPL,12,12,10",
            ]
        )
    )

    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "--strategy",
            "feature-momentum",
            "--features-data",
            str(path),
            "--symbol",
            "AAPL",
            "--fast-feature",
            "ma_fast",
            "--slow-feature",
            "ma_slow",
            "--output-dir",
            str(tmp_path / "results"),
        ],
    )

    assert result.exit_code == 0
    assert "Strategy: feature-momentum" in result.output


def test_feature_momentum_backtest_requires_feature_artifact() -> None:
    result = CliRunner().invoke(
        app,
        [
            "backtest",
            "--strategy",
            "feature-momentum",
        ],
    )

    assert result.exit_code == 2
    assert "--features-data is required for feature-momentum" in result.output
