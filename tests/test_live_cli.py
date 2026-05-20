import json

from typer.testing import CliRunner

from quant.cli import app
from quant.execution import LIVE_TRADING_CONFIRMATION


def test_live_fake_order_cli_blocks_by_default(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "live",
            "fake-order",
            "--order-output-dir",
            str(tmp_path / "orders"),
        ],
    )

    assert result.exit_code == 1
    assert "Allowed: False" in result.output
    assert not (tmp_path / "orders").exists()


def test_live_fake_order_cli_writes_artifacts_when_safety_allows(
    tmp_path,
) -> None:
    result = CliRunner().invoke(
        app,
        [
            "live",
            "fake-order",
            *_live_safety_args(),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "buy-aapl",
            "--initial-cash",
            "1000",
            "--order-output-dir",
            str(tmp_path / "orders"),
            "--fill-output-dir",
            str(tmp_path / "fills"),
            "--snapshot-output-dir",
            str(tmp_path / "snapshots"),
        ],
    )

    order_paths = list((tmp_path / "orders").glob("*.json"))
    fill_paths = list((tmp_path / "fills").glob("*.json"))
    snapshot_paths = list((tmp_path / "snapshots").glob("*.json"))

    assert result.exit_code == 0
    assert "Status: filled" in result.output
    assert len(order_paths) == 1
    assert len(fill_paths) == 1
    assert len(snapshot_paths) == 1
    order_payload = json.loads(order_paths[0].read_text())
    snapshot_payload = json.loads(snapshot_paths[0].read_text())
    assert order_payload["client_order_id"] == "buy-aapl"
    assert snapshot_payload["cash"] == 800


def test_live_fake_reconcile_cli_passes_matching_artifacts(tmp_path) -> None:
    _run_fake_order(tmp_path)
    report_path = tmp_path / "reconciliation" / "latest.json"

    result = CliRunner().invoke(
        app,
        [
            "live",
            "fake-reconcile",
            *_live_safety_args(),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "buy-aapl",
            "--initial-cash",
            "1000",
            "--order-records-dir",
            str(tmp_path / "orders"),
            "--fill-records-dir",
            str(tmp_path / "fills"),
            "--snapshot-records-dir",
            str(tmp_path / "snapshots"),
            "--output-path",
            str(report_path),
        ],
    )

    payload = json.loads(report_path.read_text())
    assert result.exit_code == 0
    assert "Status: passed" in result.output
    assert payload["status"] == "passed"
    assert payload["differences"] == []


def test_live_fake_reconcile_cli_fails_on_drift(tmp_path) -> None:
    _run_fake_order(tmp_path)
    for path in (tmp_path / "fills").glob("*.json"):
        path.unlink()
    report_path = tmp_path / "reconciliation" / "latest.json"

    result = CliRunner().invoke(
        app,
        [
            "live",
            "fake-reconcile",
            *_live_safety_args(),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "buy-aapl",
            "--initial-cash",
            "1000",
            "--order-records-dir",
            str(tmp_path / "orders"),
            "--fill-records-dir",
            str(tmp_path / "fills"),
            "--snapshot-records-dir",
            str(tmp_path / "snapshots"),
            "--output-path",
            str(report_path),
        ],
    )

    payload = json.loads(report_path.read_text())
    assert result.exit_code == 1
    assert "Status: failed" in result.output
    assert payload["status"] == "failed"
    assert payload["differences"][0]["field"].startswith("fills.")


def _run_fake_order(tmp_path) -> None:
    result = CliRunner().invoke(
        app,
        [
            "live",
            "fake-order",
            *_live_safety_args(),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "buy-aapl",
            "--initial-cash",
            "1000",
            "--order-output-dir",
            str(tmp_path / "orders"),
            "--fill-output-dir",
            str(tmp_path / "fills"),
            "--snapshot-output-dir",
            str(tmp_path / "snapshots"),
        ],
    )
    assert result.exit_code == 0


def _live_safety_args() -> list[str]:
    return [
        "--live-trading-enabled",
        "--live-trading-confirmation",
        LIVE_TRADING_CONFIRMATION,
        "--max-order-notional",
        "500",
        "--broker-name",
        "fake-live",
    ]
