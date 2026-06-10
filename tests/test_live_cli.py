import json

from typer.testing import CliRunner

import quant.cli
from quant.cli import app
from quant.execution import LIVE_TRADING_CONFIRMATION
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    Position,
)


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


def test_live_alpaca_paper_order_blocks_before_client_construction(
    monkeypatch,
    tmp_path,
) -> None:
    constructed = False

    class BlockingClient:
        def __init__(self, *args, **kwargs) -> None:
            nonlocal constructed
            constructed = True

    monkeypatch.setattr(quant.cli, "AlpacaPaperBrokerClient", BlockingClient)

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-order",
            "--order-output-dir",
            str(tmp_path / "orders"),
        ],
    )

    assert result.exit_code == 1
    assert "Allowed: False" in result.output
    assert constructed is False
    assert not (tmp_path / "orders").exists()


def test_live_alpaca_paper_order_writes_artifacts(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )
    _set_alpaca_env(monkeypatch)

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-order",
            *_live_safety_args(broker_name="alpaca-paper"),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "alpaca-client-1",
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
    assert "Alpaca paper order:" in result.output
    assert "Status: filled" in result.output
    assert len(order_paths) == 1
    assert len(fill_paths) == 1
    assert len(snapshot_paths) == 1
    assert json.loads(order_paths[0].read_text())["broker_name"] == (
        "alpaca-paper"
    )


def test_live_alpaca_paper_order_requires_credentials(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-order",
            *_live_safety_args(broker_name="alpaca-paper"),
            "--order-output-dir",
            str(tmp_path / "orders"),
        ],
    )

    assert result.exit_code != 0
    assert "QUANT_ALPACA_PAPER_API_KEY is missing" in result.output
    assert not (tmp_path / "orders").exists()


def test_live_alpaca_paper_snapshot_writes_artifact(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )
    _set_alpaca_env(monkeypatch)

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-snapshot",
            *_live_safety_args(broker_name="alpaca-paper"),
            "--snapshot-output-dir",
            str(tmp_path / "snapshots"),
        ],
    )

    snapshot_paths = list((tmp_path / "snapshots").glob("*.json"))

    assert result.exit_code == 0
    assert "Alpaca paper account snapshot:" in result.output
    assert len(snapshot_paths) == 1
    assert json.loads(snapshot_paths[0].read_text())["cash"] == 1000


def test_live_alpaca_paper_reconcile_blocks_before_client_construction(
    monkeypatch,
    tmp_path,
) -> None:
    constructed = False

    class BlockingClient:
        def __init__(self, *args, **kwargs) -> None:
            nonlocal constructed
            constructed = True

    monkeypatch.setattr(quant.cli, "AlpacaPaperBrokerClient", BlockingClient)

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-reconcile",
            "--output-path",
            str(tmp_path / "reconciliation" / "latest.json"),
        ],
    )

    assert result.exit_code == 1
    assert "Allowed: False" in result.output
    assert constructed is False
    assert not (tmp_path / "reconciliation").exists()


def test_live_alpaca_paper_reconcile_passes_matching_artifacts(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )
    _set_alpaca_env(monkeypatch)
    _run_alpaca_paper_order(tmp_path)
    report_path = tmp_path / "reconciliation" / "latest.json"

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-reconcile",
            *_live_safety_args(broker_name="alpaca-paper"),
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


def test_live_alpaca_paper_reconcile_fails_on_drift(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )
    _set_alpaca_env(monkeypatch)
    _run_alpaca_paper_order(tmp_path)
    for path in (tmp_path / "fills").glob("*.json"):
        path.unlink()
    report_path = tmp_path / "reconciliation" / "latest.json"

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-reconcile",
            *_live_safety_args(broker_name="alpaca-paper"),
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


def test_live_alpaca_paper_refresh_orders_persists_refreshed_order_and_fill(
    monkeypatch,
    tmp_path,
) -> None:
    monkeypatch.setattr(
        quant.cli,
        "AlpacaPaperBrokerClient",
        FakeAlpacaPaperBrokerClient,
    )
    _set_alpaca_env(monkeypatch)
    _run_alpaca_paper_order(tmp_path, status=LiveOrderStatus.ACCEPTED)
    order_path = next((tmp_path / "orders").glob("*.json"))
    for fill_path in (tmp_path / "fills").glob("*.json"):
        fill_path.unlink()
    FakeAlpacaPaperBrokerClient.refreshed_status = LiveOrderStatus.FILLED

    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-refresh-orders",
            *_live_safety_args(broker_name="alpaca-paper"),
            "--order-records-dir",
            str(tmp_path / "orders"),
            "--fill-records-dir",
            str(tmp_path / "fills"),
        ],
    )

    payload = json.loads(order_path.read_text())
    fill_paths = list((tmp_path / "fills").glob("*.json"))
    assert result.exit_code == 0
    assert "Refreshed orders: 1" in result.output
    assert payload["status"] == "filled"
    assert len(fill_paths) == 1


class FakeAlpacaPaperBrokerClient:
    broker_fills: tuple[LiveFillRecord, ...] = ()
    next_status: LiveOrderStatus = LiveOrderStatus.FILLED
    refreshed_status: LiveOrderStatus = LiveOrderStatus.FILLED

    def __init__(self, *, config) -> None:
        self.config = config

    def submit_market_order(
        self,
        request,
        *,
        reference_price,
        client_order_id,
        safety_check,
    ) -> LiveOrderRecord:
        record = LiveOrderRecord(
            client_order_id=client_order_id,
            broker_order_id="alpaca-order-1",
            broker_name="alpaca-paper",
            account_id=self.config.account_id,
            broker_environment="paper",
            request=request,
            reference_price=reference_price,
            notional=request.quantity * reference_price,
            safety_check=safety_check,
            status=type(self).next_status,
            raw_response_ref="alpaca-paper:order:alpaca-order-1",
        )
        type(self).broker_fills = (
            LiveFillRecord(
                order_record_id=record.id,
                client_order_id=client_order_id,
                broker_order_id="alpaca-order-1",
                broker_execution_id="alpaca-exec-1",
                broker_name="alpaca-paper",
                account_id=self.config.account_id,
                broker_environment="paper",
                symbol=request.symbol,
                side=request.side,
                quantity=request.quantity,
                price=reference_price,
                raw_response_ref="alpaca-paper:fill:alpaca-exec-1",
            ),
        )
        return record

    def account_snapshot(self) -> LiveAccountSnapshot:
        return LiveAccountSnapshot(
            broker_name="alpaca-paper",
            account_id=self.config.account_id,
            broker_environment="paper",
            cash=1000,
            buying_power=1000,
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=2,
                    average_price=100,
                    last_price=100,
                ),
            ),
        )

    def open_orders(self) -> tuple[LiveOrderRecord, ...]:
        return ()

    def has_open_orders(self) -> bool:
        return False

    def fills(self) -> tuple[LiveFillRecord, ...]:
        return type(self).broker_fills

    def remember_order_record(self, record: LiveOrderRecord) -> None:
        return None

    def refresh_order_record(
        self,
        record: LiveOrderRecord,
    ) -> LiveOrderRecord:
        return record.model_copy(
            update={"status": type(self).refreshed_status},
        )


def _set_alpaca_env(monkeypatch) -> None:
    monkeypatch.setenv("QUANT_ALPACA_PAPER_API_KEY", "paper-key")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_SECRET_KEY", "paper-secret")
    monkeypatch.setenv("QUANT_ALPACA_PAPER_ACCOUNT_ID", "acct-1")


def _run_alpaca_paper_order(
    tmp_path,
    *,
    status: LiveOrderStatus = LiveOrderStatus.FILLED,
) -> None:
    FakeAlpacaPaperBrokerClient.broker_fills = ()
    FakeAlpacaPaperBrokerClient.next_status = status
    FakeAlpacaPaperBrokerClient.refreshed_status = status
    result = CliRunner().invoke(
        app,
        [
            "live",
            "alpaca-paper-order",
            *_live_safety_args(broker_name="alpaca-paper"),
            "--symbol",
            "AAPL",
            "--side",
            "buy",
            "--quantity",
            "2",
            "--price",
            "100",
            "--client-order-id",
            "alpaca-client-1",
            "--order-output-dir",
            str(tmp_path / "orders"),
            "--fill-output-dir",
            str(tmp_path / "fills"),
            "--snapshot-output-dir",
            str(tmp_path / "snapshots"),
        ],
    )
    assert result.exit_code == 0


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


def _live_safety_args(broker_name: str = "fake-live") -> list[str]:
    return [
        "--live-trading-enabled",
        "--live-trading-confirmation",
        LIVE_TRADING_CONFIRMATION,
        "--max-order-notional",
        "500",
        "--broker-name",
        broker_name,
    ]
