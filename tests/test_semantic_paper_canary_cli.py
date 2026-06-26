"""Test translated legacy momentum semantic-paper canary preparation."""

from pathlib import Path

from typer.testing import CliRunner

from quant.cli import app
from quant.models.execution import SemanticPaperBrokerState


def test_prepare_momentum_canary_then_run_local_semantic_paper(
    tmp_path,
) -> None:
    data_path = _write_entry_prices(tmp_path)
    prepare = CliRunner().invoke(
        app,
        [
            "semantic-paper",
            "prepare-momentum-canary",
            "--request-id",
            "momentum-canary",
            "--data",
            str(data_path),
            "--symbol",
            "AAPL",
            "--quantity",
            "2",
            "--fast-window",
            "2",
            "--slow-window",
            "3",
            "--min-rows",
            "4",
            "--initial-cash",
            "1000",
            "--output-root",
            str(tmp_path / "canary"),
        ],
    )

    assert prepare.exit_code == 0
    request_path = _request_path_from_output(prepare.output)
    assert request_path.is_file()
    assert "Signal: buy" in prepare.output
    assert "Target quantity: 2" in prepare.output

    inspect = CliRunner().invoke(
        app,
        [
            "semantic-paper",
            "inspect-activated-target",
            "--request-path",
            str(request_path),
        ],
    )
    assert inspect.exit_code == 0
    assert "Valid now: yes" in inspect.output
    assert "Intended order: BUY 2 shares" in inspect.output

    run_args = [
        "semantic-paper",
        "activated-target",
        "--request-path",
        str(request_path),
        "--activation-root",
        str(tmp_path / "activation"),
        "--output-root",
        str(tmp_path / "paper-output"),
    ]
    first = CliRunner().invoke(app, run_args)
    second = CliRunner().invoke(app, run_args)

    assert first.exit_code == 0
    assert second.exit_code == 0
    assert "Execution status: satisfied" in first.output
    state = SemanticPaperBrokerState.model_validate_json(
        (tmp_path / "paper-output" / "semantic-paper" / "state.json")
        .read_text()
    )
    assert state.positions[0].quantity == 2
    assert len(state.orders) == 1
    assert len(state.fills) == 1


def test_prepare_momentum_canary_help_has_no_alpaca_or_scheduler() -> None:
    result = CliRunner().invoke(
        app, ["semantic-paper", "prepare-momentum-canary", "--help"]
    )

    assert result.exit_code == 0
    assert "alpaca" not in result.output.lower()
    assert "scheduler" not in result.output.lower()


def _write_entry_prices(tmp_path: Path) -> Path:
    path = tmp_path / "AAPL.csv"
    path.write_text(
        "date,symbol,open,high,low,close,volume\n"
        "2026-01-01,AAPL,10,11,9,10,1000\n"
        "2026-01-02,AAPL,10,11,9,10,1000\n"
        "2026-01-03,AAPL,10,11,9,10,1000\n"
        "2026-01-04,AAPL,20,21,19,20,1000\n"
    )
    return path


def _request_path_from_output(output: str) -> Path:
    for line in output.splitlines():
        if line.startswith("Request: "):
            return Path(line.removeprefix("Request: "))
    raise AssertionError(f"request path missing from output: {output}")
