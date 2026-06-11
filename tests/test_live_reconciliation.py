from quant.execution import (
    FakeLiveBrokerClient,
    LiveBrokerAdapter,
    reconcile_live_state,
    write_live_account_snapshot,
    write_live_reconciliation_report,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderRequest,
    OrderSide,
    Position,
    TradingMode,
    TradingSafetyCheck,
)


def test_reconcile_live_state_passes_when_artifacts_match_fake_broker(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert report.passed
    assert report.status == LiveReconciliationStatus.PASSED
    assert report.local_fill_count == 1
    assert report.broker_fill_count == 1
    assert report.local_position_count == 1
    assert report.broker_position_count == 1


def test_reconcile_live_state_fails_when_local_fill_is_missing(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    for path in paths["fills"].glob("*.json"):
        path.unlink()

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert not report.passed
    assert report.difference_count == 1
    assert report.differences[0].field.startswith("fills.")
    assert report.differences[0].message == "fill presence differs"


def test_reconcile_live_state_fails_when_snapshot_cash_differs(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    write_live_account_snapshot(
        LiveAccountSnapshot(
            broker_name="fake-live",
            account_id="fake-account",
            broker_environment="paper",
            cash=700,
            buying_power=700,
            positions=client.account_snapshot().positions,
        ),
        paths["snapshots"],
    )

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert not report.passed
    assert any(diff.field == "cash" for diff in report.differences)


def test_reconcile_live_state_fails_when_snapshot_position_differs(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    write_live_account_snapshot(
        LiveAccountSnapshot(
            broker_name="fake-live",
            account_id="fake-account",
            broker_environment="paper",
            cash=800,
            buying_power=800,
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=1,
                    average_price=100,
                    last_price=100,
                ),
            ),
        ),
        paths["snapshots"],
    )

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert not report.passed
    assert any(
        diff.field == "positions.AAPL.quantity"
        for diff in report.differences
    )


def test_reconcile_live_state_observes_market_marks_without_failing(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    broker_snapshot = client.account_snapshot()
    broker_position = broker_snapshot.positions[0]
    write_live_account_snapshot(
        LiveAccountSnapshot(
            broker_name="fake-live",
            account_id="fake-account",
            broker_environment="paper",
            cash=broker_snapshot.cash,
            buying_power=broker_snapshot.buying_power + 5,
            positions=(
                Position(
                    symbol=broker_position.symbol,
                    quantity=broker_position.quantity,
                    average_price=broker_position.average_price,
                    last_price=broker_position.last_price + 2,
                ),
            ),
        ),
        paths["snapshots"],
    )

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert report.passed
    assert report.difference_count == 0
    assert report.observation_count == 2
    assert {observation.field for observation in report.observations} == {
        "buying_power",
        "positions.AAPL.last_price",
    }


def test_reconcile_live_state_fails_when_average_price_differs(
    tmp_path,
) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    broker_snapshot = client.account_snapshot()
    broker_position = broker_snapshot.positions[0]
    write_live_account_snapshot(
        LiveAccountSnapshot(
            broker_name="fake-live",
            account_id="fake-account",
            broker_environment="paper",
            cash=broker_snapshot.cash,
            buying_power=broker_snapshot.buying_power,
            positions=(
                Position(
                    symbol=broker_position.symbol,
                    quantity=broker_position.quantity,
                    average_price=broker_position.average_price + 1,
                    last_price=broker_position.last_price,
                ),
            ),
        ),
        paths["snapshots"],
    )

    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    assert not report.passed
    assert any(
        difference.field == "positions.AAPL.average_price"
        for difference in report.differences
    )


def test_write_live_reconciliation_report_round_trips(tmp_path) -> None:
    client, paths = _write_matching_live_artifacts(tmp_path)
    report = reconcile_live_state(
        client=client,
        order_records_dir=paths["orders"],
        fill_records_dir=paths["fills"],
        snapshot_records_dir=paths["snapshots"],
    )

    path = write_live_reconciliation_report(
        report,
        tmp_path / "reconciliation" / "latest.json",
    )
    loaded = LiveReconciliationReport.model_validate_json(path.read_text())

    assert loaded == report


def _write_matching_live_artifacts(tmp_path):
    client = FakeLiveBrokerClient(initial_cash=1_000)
    paths = {
        "orders": tmp_path / "orders",
        "fills": tmp_path / "fills",
        "snapshots": tmp_path / "snapshots",
    }
    adapter = LiveBrokerAdapter(
        client=client,
        order_output_dir=paths["orders"],
        fill_output_dir=paths["fills"],
        snapshot_output_dir=paths["snapshots"],
    )
    adapter.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="buy-aapl",
        safety_check=TradingSafetyCheck(
            mode=TradingMode.LIVE,
            allowed=True,
        ),
    )
    adapter.account_snapshot()
    return client, paths
