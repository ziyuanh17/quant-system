from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from quant.execution import (
    map_alpaca_account_snapshot,
    map_alpaca_fill_records,
    map_alpaca_order_record,
    map_alpaca_order_status,
    map_alpaca_position,
    map_order_request_to_alpaca_market_order,
)
from quant.models.execution import (
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)


@pytest.mark.parametrize(
    ("alpaca_status", "expected"),
    [
        ("filled", LiveOrderStatus.FILLED),
        ("partially_filled", LiveOrderStatus.PARTIALLY_FILLED),
        ("canceled", LiveOrderStatus.CANCELLED),
        ("cancelled", LiveOrderStatus.CANCELLED),
        ("expired", LiveOrderStatus.CANCELLED),
        ("rejected", LiveOrderStatus.REJECTED),
        ("new", LiveOrderStatus.ACCEPTED),
        ("accepted", LiveOrderStatus.ACCEPTED),
        ("pending_new", LiveOrderStatus.ACCEPTED),
        ("accepted_for_bidding", LiveOrderStatus.ACCEPTED),
        ("pending_cancel", LiveOrderStatus.ACCEPTED),
        ("pending_replace", LiveOrderStatus.ACCEPTED),
        ("done_for_day", LiveOrderStatus.UNKNOWN),
        ("replaced", LiveOrderStatus.UNKNOWN),
        ("stopped", LiveOrderStatus.UNKNOWN),
        ("suspended", LiveOrderStatus.UNKNOWN),
        ("calculated", LiveOrderStatus.UNKNOWN),
        ("held", LiveOrderStatus.UNKNOWN),
        ("mystery", LiveOrderStatus.UNKNOWN),
    ],
)
def test_map_alpaca_order_status(
    alpaca_status: str,
    expected: LiveOrderStatus,
) -> None:
    assert map_alpaca_order_status(alpaca_status) == expected


def test_map_order_request_to_alpaca_market_order() -> None:
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)

    alpaca_request = map_order_request_to_alpaca_market_order(
        request,
        client_order_id="client-1",
    )

    assert alpaca_request.symbol == "AAPL"
    assert alpaca_request.side == "buy"
    assert alpaca_request.qty == 2
    assert alpaca_request.time_in_force == "day"
    assert alpaca_request.client_order_id == "client-1"


def test_map_alpaca_order_record_from_object() -> None:
    submitted_at = datetime(2026, 5, 20, tzinfo=UTC)
    order = SimpleNamespace(
        id="alpaca-order-1",
        client_order_id="client-1",
        status="accepted",
        submitted_at=submitted_at,
        updated_at="2026-05-20T12:00:00+00:00",
    )

    record = map_alpaca_order_record(
        order,
        request=OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=2,
        ),
        reference_price=100.25,
        safety_check=_live_check(),
        account_id="acct-1",
    )

    assert record.client_order_id == "client-1"
    assert record.broker_order_id == "alpaca-order-1"
    assert record.broker_name == "alpaca-paper"
    assert record.account_id == "acct-1"
    assert record.broker_environment == "paper"
    assert record.notional == 200.5
    assert record.status == LiveOrderStatus.ACCEPTED
    assert record.submitted_at == submitted_at
    assert record.broker_updated_at == datetime(
        2026,
        5,
        20,
        12,
        tzinfo=UTC,
    )


def test_map_alpaca_order_record_requires_client_order_id() -> None:
    with pytest.raises(ValueError, match="client_order_id"):
        map_alpaca_order_record(
            {"id": "alpaca-order-1", "status": "accepted"},
            request=OrderRequest(
                symbol="AAPL",
                side=OrderSide.BUY,
                quantity=2,
            ),
            reference_price=100,
            safety_check=_live_check(),
            account_id="acct-1",
        )


def test_map_alpaca_fill_records_from_filled_order() -> None:
    order = {
        "id": "alpaca-order-1",
        "client_order_id": "client-1",
        "status": "filled",
        "filled_qty": "2",
        "filled_avg_price": "100.25",
        "filled_at": "2026-05-20T12:00:00+00:00",
    }
    order_record = map_alpaca_order_record(
        order,
        request=OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=2,
        ),
        reference_price=100.25,
        safety_check=_live_check(),
        account_id="acct-1",
    )

    fills = map_alpaca_fill_records(order, order_record=order_record)

    assert len(fills) == 1
    assert fills[0].client_order_id == "client-1"
    assert fills[0].broker_order_id == "alpaca-order-1"
    assert fills[0].quantity == 2
    assert fills[0].price == 100.25
    assert fills[0].notional == 200.5


def test_map_alpaca_fill_records_skips_unfilled_order() -> None:
    order_record = map_alpaca_order_record(
        {
            "id": "alpaca-order-1",
            "client_order_id": "client-1",
            "status": "accepted",
        },
        request=OrderRequest(
            symbol="AAPL",
            side=OrderSide.BUY,
            quantity=2,
        ),
        reference_price=100,
        safety_check=_live_check(),
        account_id="acct-1",
    )

    assert map_alpaca_fill_records({}, order_record=order_record) == ()


def test_map_alpaca_account_snapshot_parses_numeric_strings() -> None:
    account = SimpleNamespace(
        id="acct-1",
        cash="1000.25",
        buying_power="2000.50",
    )
    positions = [
        SimpleNamespace(
            symbol="AAPL",
            qty="2",
            avg_entry_price="100.25",
            current_price="101.50",
        ),
    ]

    snapshot = map_alpaca_account_snapshot(account, positions)

    assert snapshot.broker_name == "alpaca-paper"
    assert snapshot.account_id == "acct-1"
    assert snapshot.cash == 1000.25
    assert snapshot.buying_power == 2000.5
    assert snapshot.positions[0].symbol == "AAPL"
    assert snapshot.positions[0].quantity == 2
    assert snapshot.positions[0].average_price == 100.25
    assert snapshot.positions[0].last_price == 101.5


def test_map_alpaca_position_can_use_market_value_for_last_price() -> None:
    position = {
        "symbol": "AAPL",
        "qty": "2",
        "avg_entry_price": "100",
        "market_value": "210",
    }

    mapped = map_alpaca_position(position)

    assert mapped.last_price == 105


def _live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)
