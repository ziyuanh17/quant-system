"""Test alpaca paper client behavior and safety invariants."""

from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any, cast

import pytest

from quant.execution import (
    LiveBrokerAdapter,
    append_execution_leg_event,
    current_execution_leg_status,
    load_live_order_records,
)
from quant.execution.alpaca_paper import (
    AlpacaPaperBrokerClient,
    AlpacaPaperConfig,
)
from quant.execution.alpaca_sdk import AlpacaTradingSdk
from quant.execution.target_lifecycle import run_multi_leg_transition
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    OrderRequest,
    OrderSide,
    TradingMode,
    TradingSafetyCheck,
)
from quant.models.execution_lifecycle import (
    ExecutionLegStatus,
    ExecutionTransitionLeg,
    ExecutionTransitionPlan,
)


def test_alpaca_paper_config_requires_credentials() -> None:
    with pytest.raises(ValueError, match="api_key"):
        AlpacaPaperConfig(
            api_key="",
            secret_key="paper-secret",
            account_id="acct-1",
        )


def test_alpaca_paper_client_constructs_sdk_client_in_paper_mode() -> None:
    config = AlpacaPaperConfig(
        api_key="paper-key",
        secret_key="paper-secret",
        account_id="acct-1",
        url_override="https://example.test",
    )

    client = AlpacaPaperBrokerClient(config=config, sdk=_fake_sdk())

    trading_client = client.trading_client_for_testing
    assert isinstance(trading_client, FakeTradingClient)
    assert trading_client.init_kwargs == {
        "api_key": "paper-key",
        "secret_key": "paper-secret",
        "paper": True,
        "url_override": "https://example.test",
    }


def test_alpaca_paper_client_can_use_injected_trading_client() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )

    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    assert client.trading_client_for_testing is trading_client


def test_alpaca_paper_client_submits_market_order_and_maps_fill() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )

    record = client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100.25,
        client_order_id="client-1",
        safety_check=_allowed_live_check(),
    )

    assert isinstance(trading_client.submitted_orders[0], FakeMarketOrder)
    assert trading_client.submitted_orders[0].kwargs["symbol"] == "AAPL"
    assert trading_client.submitted_orders[0].kwargs["side"].value == "buy"
    assert record.status == LiveOrderStatus.FILLED
    assert record.broker_name == "alpaca-paper"
    assert record.account_id == "acct-1"
    assert record.notional == 200.5
    assert len(client.fills()) == 1
    assert client.fills()[0].client_order_id == "client-1"
    assert client.fills()[0].notional == 200.5


def test_alpaca_paper_client_maps_account_snapshot() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.account = SimpleNamespace(
        id="acct-1",
        cash="1000.25",
        buying_power="2000.50",
    )
    trading_client.positions = [
        SimpleNamespace(
            symbol="AAPL",
            qty="2",
            avg_entry_price="100.25",
            current_price="101.50",
        ),
    ]
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    snapshot = client.account_snapshot()

    assert snapshot.broker_name == "alpaca-paper"
    assert snapshot.account_id == "acct-1"
    assert snapshot.cash == 1000.25
    assert snapshot.buying_power == 2000.5
    assert snapshot.positions[0].symbol == "AAPL"


def test_alpaca_paper_client_maps_asset_trading_details() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.assets["AAPL"] = SimpleNamespace(
        symbol="AAPL",
        tradable=True,
        shortable=True,
        easy_to_borrow=False,
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    details = client.asset_trading_details("AAPL")

    assert details.symbol == "AAPL"
    assert details.tradable is True
    assert details.shortable is True
    assert details.easy_to_borrow is False


def test_alpaca_paper_client_open_orders_maps_known_orders_only() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.next_order_status = "accepted"
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )

    client.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        reference_price=100,
        client_order_id="client-1",
        safety_check=_allowed_live_check(),
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="unknown-order",
            client_order_id="unknown-client-id",
            status="accepted",
        )
    )

    open_orders = client.open_orders()

    assert len(open_orders) == 1
    assert open_orders[0].client_order_id == "client-1"
    assert open_orders[0].status == LiveOrderStatus.ACCEPTED


def test_alpaca_paper_client_detects_unknown_open_broker_orders() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="unknown-order",
            client_order_id="unknown-client-id",
            status="accepted",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    assert client.has_open_orders() is True


def test_alpaca_paper_client_refreshes_known_fills_from_polled_orders() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2)
    order_record = LiveOrderRecord(
        client_order_id="client-1",
        broker_order_id="alpaca-order-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=request,
        reference_price=100.25,
        notional=200.5,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.FILLED,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="alpaca-order-1",
            client_order_id="client-1",
            status="filled",
            filled_qty="2",
            filled_avg_price="100.25",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    client.remember_order_record(order_record)
    fills = client.fills()

    assert len(fills) == 1
    assert fills[0].client_order_id == "client-1"
    assert fills[0].notional == 200.5


def test_alpaca_client_refreshes_historical_fill_by_broker_order_id() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    order_record = LiveOrderRecord(
        client_order_id="historical-client-1",
        broker_order_id="historical-order-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=OrderRequest(
            symbol="F",
            side=OrderSide.BUY,
            quantity=1,
        ),
        reference_price=14.33,
        notional=14.33,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.FILLED,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="historical-order-1",
            client_order_id="historical-client-1",
            status="filled",
            filled_qty="1",
            filled_avg_price="14.33",
        )
    )
    trading_client.default_order_ids = set()
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    client.remember_order_record(order_record)
    fills = client.fills()

    assert trading_client.get_orders_calls == 0
    assert trading_client.get_order_by_id_calls == ["historical-order-1"]
    assert len(fills) == 1
    assert fills[0].symbol == "F"
    assert fills[0].quantity == 1
    assert fills[0].price == 14.33


def test_alpaca_paper_client_refreshes_terminal_order_by_broker_id() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1)
    order_record = LiveOrderRecord(
        client_order_id="client-1",
        broker_order_id="alpaca-order-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=request,
        reference_price=100,
        notional=100,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.ACCEPTED,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="alpaca-order-1",
            client_order_id="client-1",
            status="canceled",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )

    client.remember_order_record(order_record)
    refreshed = client.refresh_order_record(order_record)

    assert refreshed.id == order_record.id
    assert refreshed.status == LiveOrderStatus.CANCELLED
    assert refreshed.client_order_id == "client-1"
    assert refreshed.broker_order_id == "alpaca-order-1"


def test_alpaca_paper_client_recovers_order_by_client_id() -> None:
    trading_client = FakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
    )
    request = OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1)
    order_record = LiveOrderRecord(
        client_order_id="client-1",
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        request=request,
        reference_price=100,
        notional=100,
        safety_check=_allowed_live_check(),
        status=LiveOrderStatus.UNKNOWN,
    )
    trading_client.orders.append(
        SimpleNamespace(
            id="alpaca-order-1",
            client_order_id="client-1",
            status="filled",
            filled_qty="1",
            filled_avg_price="100",
        )
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
    )
    client.remember_order_record(order_record)

    recovered = client.orders_by_client_order_id("client-1")

    assert len(recovered) == 1
    assert recovered[0].id == order_record.id
    assert recovered[0].broker_order_id == "alpaca-order-1"
    assert recovered[0].status == LiveOrderStatus.FILLED
    assert trading_client.get_order_by_client_id_calls == ["client-1"]


def test_alpaca_paper_client_lookup_requires_durable_context() -> None:
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=FakeTradingClient(
            api_key="unused",
            secret_key="unused",
            paper=True,
        ),
    )

    with pytest.raises(RuntimeError, match="durable order context"):
        client.orders_by_client_order_id("unknown")


def test_alpaca_shaped_transition_recovers_leg_by_client_id(
    tmp_path,
) -> None:
    trading_client = TransitionFakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
        initial_quantity=-1,
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )
    adapter = LiveBrokerAdapter(
        client=client,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
    )
    transition = _short_to_long_transition()

    first = run_multi_leg_transition(
        transition=transition,
        broker=_SubmitThenRaiseOnce(adapter),
        reconciliation_client=client,
        artifact_root=tmp_path / "lifecycle",
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_allowed_live_check(),
        evaluated_at=_now(),
    )
    second = run_multi_leg_transition(
        transition=transition,
        broker=adapter,
        reconciliation_client=client,
        artifact_root=tmp_path / "lifecycle",
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_allowed_live_check(),
        evaluated_at=_now(),
    )

    assert first.leg_statuses == (
        ExecutionLegStatus.AMBIGUOUS,
        ExecutionLegStatus.PLANNED,
    )
    assert second.leg_statuses == (
        ExecutionLegStatus.RECONCILED,
        ExecutionLegStatus.RECONCILED,
    )
    assert trading_client.get_order_by_client_id_calls == [
        transition.legs[0].client_order_id
    ]
    assert [
        order.client_order_id
        for order in load_live_order_records(tmp_path / "orders")
    ] == [
        transition.legs[0].client_order_id,
        transition.legs[1].client_order_id,
    ]
    assert trading_client.submitted_client_order_ids == [
        transition.legs[0].client_order_id,
        transition.legs[1].client_order_id,
    ]
    assert client.account_snapshot().positions[0].quantity == 2


def test_alpaca_shaped_transition_blocks_ambiguous_lookup_without_resubmit(
    tmp_path,
) -> None:
    trading_client = TransitionFakeTradingClient(
        api_key="unused",
        secret_key="unused",
        paper=True,
        initial_quantity=-1,
    )
    client = AlpacaPaperBrokerClient(
        config=AlpacaPaperConfig(
            api_key="paper-key",
            secret_key="paper-secret",
            account_id="acct-1",
        ),
        trading_client=trading_client,
        sdk=_fake_sdk(),
    )
    transition = _short_to_long_transition()
    artifact_root = tmp_path / "lifecycle"
    append_execution_leg_event(
        transition=transition,
        artifact_root=artifact_root,
        leg_id=transition.legs[0].leg_id,
        new_status=ExecutionLegStatus.SUBMISSION_PENDING,
        occurred_at=_now(),
        reason="test submission intent",
    )
    append_execution_leg_event(
        transition=transition,
        artifact_root=artifact_root,
        leg_id=transition.legs[0].leg_id,
        new_status=ExecutionLegStatus.AMBIGUOUS,
        occurred_at=_now(),
        reason="test ambiguous submission",
    )

    result = run_multi_leg_transition(
        transition=transition,
        broker=LiveBrokerAdapter(client=client),
        reconciliation_client=client,
        artifact_root=artifact_root,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_dir=tmp_path / "reconciliations",
        reference_price=100,
        safety_check=_allowed_live_check(),
        evaluated_at=_now(),
    )

    assert result.leg_statuses == (
        ExecutionLegStatus.BLOCKED,
        ExecutionLegStatus.PLANNED,
    )
    assert trading_client.submitted_orders == []
    assert current_execution_leg_status(
        transition,
        artifact_root,
        transition.legs[0].leg_id,
    ) == ExecutionLegStatus.BLOCKED


class FakeEnum:
    def __init__(self, value: str) -> None:
        self.value = value


class FakeMarketOrder:
    def __init__(self, **kwargs: Any) -> None:
        self.kwargs = kwargs


class FakeTradingClient:
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        paper: bool,
        url_override: str | None = None,
    ) -> None:
        self.init_kwargs = {
            "api_key": api_key,
            "secret_key": secret_key,
            "paper": paper,
            "url_override": url_override,
        }
        self.submitted_orders: list[object] = []
        self.orders: list[object] = []
        self.positions: list[object] = []
        self.assets: dict[str, object] = {}
        self.account = SimpleNamespace(
            id="acct-1",
            cash="1000",
            buying_power="1000",
        )
        self.next_order_status = "filled"
        self.default_order_ids: set[str] | None = None
        self.get_orders_calls = 0
        self.get_order_by_id_calls: list[str] = []
        self.get_order_by_client_id_calls: list[str] = []

    def submit_order(self, order_data: object) -> object:
        if not isinstance(order_data, FakeMarketOrder):
            raise TypeError("expected FakeMarketOrder")
        self.submitted_orders.append(order_data)
        order = SimpleNamespace(
            id=f"alpaca-order-{len(self.orders) + 1}",
            client_order_id=order_data.kwargs["client_order_id"],
            status=self.next_order_status,
            filled_qty=str(order_data.kwargs["qty"]),
            filled_avg_price="100.25",
        )
        self.orders.append(order)
        return order

    def get_orders(self, filter: object | None = None) -> list[object]:
        self.get_orders_calls += 1
        if self.default_order_ids is not None:
            return [
                order
                for order in self.orders
                if cast(Any, order).id in self.default_order_ids
            ]
        return self.orders

    def get_order_by_id(self, order_id: str) -> object:
        self.get_order_by_id_calls.append(order_id)
        for order in self.orders:
            order_id_value = cast(Any, order).id
            if order_id_value == order_id:
                return order
        raise ValueError(f"unknown order: {order_id}")

    def get_order_by_client_id(self, client_id: str) -> object:
        self.get_order_by_client_id_calls.append(client_id)
        for order in self.orders:
            if cast(Any, order).client_order_id == client_id:
                return order
        raise ValueError(f"unknown client order: {client_id}")

    def get_account(self) -> object:
        return self.account

    def get_all_positions(self) -> list[object]:
        return self.positions

    def get_asset(self, symbol_or_asset_id: str) -> object:
        return self.assets[symbol_or_asset_id]


class TransitionFakeTradingClient(FakeTradingClient):
    def __init__(
        self,
        *,
        api_key: str,
        secret_key: str,
        paper: bool,
        initial_quantity: int,
    ) -> None:
        super().__init__(
            api_key=api_key,
            secret_key=secret_key,
            paper=paper,
        )
        self.quantity = initial_quantity
        self.submitted_client_order_ids: list[str] = []
        self._sync_positions()

    def submit_order(self, order_data: object) -> object:
        order = super().submit_order(order_data)
        if not isinstance(order_data, FakeMarketOrder):
            raise TypeError("expected FakeMarketOrder")
        self.submitted_client_order_ids.append(
            order_data.kwargs["client_order_id"]
        )
        side = order_data.kwargs["side"].value
        qty = int(order_data.kwargs["qty"])
        if side == "buy":
            self.quantity += qty
        else:
            self.quantity -= qty
        self._sync_positions()
        return order

    def _sync_positions(self) -> None:
        if self.quantity == 0:
            self.positions = []
            return
        self.positions = [
            SimpleNamespace(
                symbol="AAPL",
                qty=str(self.quantity),
                avg_entry_price="100",
                current_price="100",
            )
        ]


class _SubmitThenRaiseOnce:
    def __init__(self, delegate: LiveBrokerAdapter) -> None:
        self.delegate = delegate
        self.raised = False

    def submit_market_order(
        self,
        request: OrderRequest,
        *,
        reference_price: float,
        client_order_id: str,
        safety_check: TradingSafetyCheck,
    ) -> LiveOrderRecord:
        order = self.delegate.submit_market_order(
            request,
            reference_price=reference_price,
            client_order_id=client_order_id,
            safety_check=safety_check,
        )
        if not self.raised:
            self.raised = True
            raise RuntimeError("lost response after Alpaca accepted leg")
        return order

    def account_snapshot(self):
        return self.delegate.account_snapshot()

    def has_open_orders(self) -> bool:
        return self.delegate.has_open_orders()

    def orders_by_client_order_id(
        self,
        client_order_id: str,
    ) -> tuple[LiveOrderRecord, ...]:
        return self.delegate.orders_by_client_order_id(client_order_id)


def _fake_sdk() -> AlpacaTradingSdk:
    return AlpacaTradingSdk(
        TradingClient=FakeTradingClient,
        MarketOrderRequest=FakeMarketOrder,
        OrderSide=FakeEnum,
        TimeInForce=FakeEnum,
    )


def _allowed_live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)


def _short_to_long_transition() -> ExecutionTransitionPlan:
    return ExecutionTransitionPlan(
        transition_plan_id="transition-execution-risk-1-r1",
        execution_plan_id="execution-risk-1-r1",
        risk_target_id="risk-1",
        risk_target_revision=1,
        symbol="AAPL",
        current_quantity=-1,
        target_quantity=2,
        legs=(
            ExecutionTransitionLeg(
                leg_id="execution-risk-1-r1-leg-1",
                leg_index=1,
                semantic="close_short",
                order_request=OrderRequest(
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    quantity=1,
                ),
                required_start_quantity=-1,
                required_end_quantity=0,
                client_order_id="target-risk-1-r1-leg-1",
            ),
            ExecutionTransitionLeg(
                leg_id="execution-risk-1-r1-leg-2",
                leg_index=2,
                semantic="open_long",
                order_request=OrderRequest(
                    symbol="AAPL",
                    side=OrderSide.BUY,
                    quantity=2,
                ),
                required_start_quantity=0,
                required_end_quantity=2,
                client_order_id="target-risk-1-r1-leg-2",
            ),
        ),
        created_at=_now(),
        reason="test transition",
    )


def _now() -> datetime:
    return datetime(2026, 7, 1, 12, tzinfo=UTC)
