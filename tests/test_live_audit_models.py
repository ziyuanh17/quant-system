"""Test live audit models behavior and safety invariants."""

from quant.execution import (
    write_live_account_snapshot,
    write_live_fill_record,
    write_live_order_record,
    write_live_reconciliation_report,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    LiveReconciliationDifference,
    LiveReconciliationObservation,
    LiveReconciliationReport,
    LiveReconciliationStatus,
    OrderRequest,
    OrderSide,
    Position,
    TradingMode,
    TradingSafetyCheck,
)


def test_live_order_record_round_trips_without_broker_credentials(
    tmp_path,
) -> None:
    record = LiveOrderRecord(
        client_order_id="momentum-AAPL-2024-01-25-buy",
        broker_order_id="broker-order-1",
        broker_name="alpaca",
        account_id="acct-1234",
        broker_environment="paper",
        request=OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=2,
        ),
        reference_price=100,
        notional=200,
        safety_check=TradingSafetyCheck(
            mode=TradingMode.LIVE,
            allowed=True,
        ),
        status=LiveOrderStatus.ACCEPTED,
        raw_response_ref="sha256:broker-response",
    )

    path = write_live_order_record(record, tmp_path / "orders")
    loaded = LiveOrderRecord.model_validate_json(path.read_text())

    assert loaded == record
    assert loaded.account_id == "acct-1234"
    assert "API" not in path.read_text()


def test_live_fill_and_account_snapshot_artifacts_round_trip(
    tmp_path,
) -> None:
    fill = LiveFillRecord(
        order_record_id="local-order-1",
        client_order_id="client-order-1",
        broker_order_id="broker-order-1",
        broker_execution_id="exec-1",
        broker_name="alpaca",
        account_id="acct-1234",
        broker_environment="paper",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=2,
        price=100,
        commission=0.5,
    )
    snapshot = LiveAccountSnapshot(
        broker_name="alpaca",
        account_id="acct-1234",
        broker_environment="paper",
        cash=800,
        buying_power=1600,
        positions=(
            Position(
                symbol="AAPL",
                quantity=2,
                average_price=100,
                last_price=101,
            ),
        ),
        open_order_ids=("broker-order-1",),
    )

    fill_path = write_live_fill_record(fill, tmp_path / "fills")
    snapshot_path = write_live_account_snapshot(
        snapshot,
        tmp_path / "account_snapshots",
    )

    loaded_fill = LiveFillRecord.model_validate_json(fill_path.read_text())
    loaded_snapshot = LiveAccountSnapshot.model_validate_json(
        snapshot_path.read_text()
    )

    assert loaded_fill.notional == 200
    assert loaded_snapshot.equity == 1002
    assert loaded_snapshot.open_order_ids == ("broker-order-1",)


def test_live_reconciliation_report_tracks_differences(tmp_path) -> None:
    report = LiveReconciliationReport(
        broker_name="alpaca",
        account_id="acct-1234",
        broker_environment="paper",
        local_order_count=1,
        broker_order_count=1,
        local_fill_count=0,
        broker_fill_count=1,
        local_position_count=0,
        broker_position_count=1,
        status=LiveReconciliationStatus.FAILED,
        differences=(
            LiveReconciliationDifference(
                field="fills",
                local_value="0",
                broker_value="1",
                message="broker has a fill missing from local artifacts",
            ),
        ),
        observations=(
            LiveReconciliationObservation(
                field="positions.AAPL.last_price",
                local_value="100.000000",
                broker_value="101.000000",
                message=(
                    "volatile market-derived value changed between snapshots"
                ),
            ),
        ),
    )

    path = write_live_reconciliation_report(
        report,
        tmp_path / "reconciliation" / "latest.json",
    )
    loaded = LiveReconciliationReport.model_validate_json(path.read_text())

    assert not loaded.passed
    assert loaded.difference_count == 1
    assert loaded.observation_count == 1
    assert loaded.differences[0].field == "fills"
