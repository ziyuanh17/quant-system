"""Test live broker adapter behavior and safety invariants."""

import pytest

from quant.execution import (
    FakeLiveBrokerClient,
    LiveBrokerAdapter,
    LiveTradingNotAllowedError,
)
from quant.models.execution import (
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)


def test_live_broker_adapter_blocks_before_client_submission() -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)
    adapter = LiveBrokerAdapter(client=client)

    with pytest.raises(LiveTradingNotAllowedError):
        adapter.submit_market_order(
            OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
            reference_price=100,
            client_order_id="blocked",
            safety_check=TradingSafetyCheck(
                mode=TradingMode.DRY_RUN,
                allowed=True,
            ),
        )

    assert client.fills() == ()
    assert client.account_snapshot().cash == 1_000


def test_live_broker_adapter_submits_allowed_live_order() -> None:
    adapter = LiveBrokerAdapter(
        client=FakeLiveBrokerClient(initial_cash=1_000)
    )

    record = adapter.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="buy-aapl",
        safety_check=_allowed_live_check(),
    )
    snapshot = adapter.account_snapshot()

    assert record.status == LiveOrderStatus.FILLED
    assert snapshot.cash == 800
    assert adapter.fills()[0].client_order_id == "buy-aapl"
    assert adapter.open_orders() == ()


def test_live_broker_adapter_preserves_client_id_idempotency() -> None:
    adapter = LiveBrokerAdapter(
        client=FakeLiveBrokerClient(initial_cash=1_000)
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)

    first = adapter.submit_market_order(
        request,
        reference_price=100,
        client_order_id="same-client-id",
        safety_check=_allowed_live_check(),
    )
    second = adapter.submit_market_order(
        request,
        reference_price=100,
        client_order_id="same-client-id",
        safety_check=_allowed_live_check(),
    )

    assert second == first
    assert len(adapter.fills()) == 1
    assert adapter.account_snapshot().cash == 800


def test_live_broker_adapter_writes_optional_artifacts(tmp_path) -> None:
    adapter = LiveBrokerAdapter(
        client=FakeLiveBrokerClient(initial_cash=1_000),
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "account_snapshots",
    )

    adapter.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="artifact-order",
        safety_check=_allowed_live_check(),
    )
    adapter.account_snapshot()
    adapter.fills()

    order_paths = list((tmp_path / "orders").glob("*.json"))
    fill_paths = list((tmp_path / "fills").glob("*.json"))
    snapshot_paths = list((tmp_path / "account_snapshots").glob("*.json"))

    assert len(order_paths) == 1
    assert len(fill_paths) == 1
    assert len(snapshot_paths) == 1
    assert (
        LiveOrderRecord.model_validate_json(order_paths[0].read_text()).status
        == LiveOrderStatus.FILLED
    )
    assert (
        LiveFillRecord.model_validate_json(
            fill_paths[0].read_text()
        ).client_order_id
        == "artifact-order"
    )
    assert (
        LiveAccountSnapshot.model_validate_json(
            snapshot_paths[0].read_text()
        ).cash
        == 800
    )


def test_live_broker_adapter_does_not_duplicate_fill_across_processes(
    tmp_path,
) -> None:
    client = FakeLiveBrokerClient(initial_cash=1_000)
    fill_dir = tmp_path / "fills"
    first_adapter = LiveBrokerAdapter(
        client=client,
        fill_output_dir=fill_dir,
    )
    first_adapter.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
        reference_price=100,
        client_order_id="artifact-order",
        safety_check=_allowed_live_check(),
    )

    second_adapter = LiveBrokerAdapter(
        client=client,
        fill_output_dir=fill_dir,
    )
    second_adapter.fills()

    assert len(list(fill_dir.glob("*.json"))) == 1


def _allowed_live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)
