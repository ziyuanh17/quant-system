import json

import pytest

from quant.execution import (
    ALPACA_PAPER_REHEARSAL_CONFIRMATION,
    FakeLiveBrokerClient,
    LiveRehearsalBlockedError,
    run_alpaca_paper_order_rehearsal,
)
from quant.models.execution import (
    LiveOrderRecord,
    LiveOrderStatus,
    Position,
    TradingMode,
    TradingSafetyCheck,
)


def test_rehearsal_blocks_before_submission_when_protected_position_differs(
    tmp_path,
) -> None:
    client = FakeLiveBrokerClient(
        initial_cash=1000,
        positions=(_position("AAPL", -2),),
    )

    with pytest.raises(
        LiveRehearsalBlockedError,
        match="protected position AAPL expected -1 but observed -2",
    ):
        run_alpaca_paper_order_rehearsal(
            client=client,
            safety_check=_allowed_live_check(),
            symbol="MSFT",
            reference_price=100,
            client_order_id="rehearsal-msft-1",
            protected_positions={"AAPL": -1},
            confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
            order_output_dir=tmp_path / "orders",
            fill_output_dir=tmp_path / "fills",
            snapshot_output_dir=tmp_path / "snapshots",
            reconciliation_output_path=tmp_path / "reconciliation.json",
            rehearsal_output_dir=tmp_path / "rehearsals",
            max_order_notional=150,
            order_poll_interval_seconds=0,
        )

    assert client.fills() == ()
    assert not (tmp_path / "orders").exists()


def test_rehearsal_blocks_when_rehearsal_symbol_already_has_position(
    tmp_path,
) -> None:
    client = FakeLiveBrokerClient(
        initial_cash=1000,
        positions=(
            _position("AAPL", -1),
            _position("MSFT", 1),
        ),
    )

    with pytest.raises(
        LiveRehearsalBlockedError,
        match="rehearsal symbol MSFT already has a position",
    ):
        run_alpaca_paper_order_rehearsal(
            client=client,
            safety_check=_allowed_live_check(),
            symbol="MSFT",
            reference_price=100,
            client_order_id="rehearsal-msft-1",
            protected_positions={"AAPL": -1},
            confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
            order_output_dir=tmp_path / "orders",
            fill_output_dir=tmp_path / "fills",
            snapshot_output_dir=tmp_path / "snapshots",
            reconciliation_output_path=tmp_path / "reconciliation.json",
            rehearsal_output_dir=tmp_path / "rehearsals",
            max_order_notional=150,
            order_poll_interval_seconds=0,
        )

    assert client.fills() == ()


def test_rehearsal_blocks_non_paper_broker_environment(tmp_path) -> None:
    client = FakeLiveBrokerClient(
        initial_cash=1000,
        broker_environment="live",
        positions=(_position("AAPL", -1),),
    )

    with pytest.raises(
        LiveRehearsalBlockedError,
        match="requires a paper broker environment",
    ):
        run_alpaca_paper_order_rehearsal(
            client=client,
            safety_check=_allowed_live_check(),
            symbol="MSFT",
            reference_price=100,
            client_order_id="rehearsal-msft-1",
            protected_positions={"AAPL": -1},
            confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
            order_output_dir=tmp_path / "orders",
            fill_output_dir=tmp_path / "fills",
            snapshot_output_dir=tmp_path / "snapshots",
            reconciliation_output_path=tmp_path / "reconciliation.json",
            rehearsal_output_dir=tmp_path / "rehearsals",
            max_order_notional=150,
            order_poll_interval_seconds=0,
        )

    assert client.fills() == ()
    assert not (tmp_path / "orders").exists()


def test_rehearsal_blocks_case_insensitive_protected_symbol(tmp_path) -> None:
    client = FakeLiveBrokerClient(
        initial_cash=1000,
        positions=(_position("AAPL", -1),),
    )

    with pytest.raises(
        LiveRehearsalBlockedError,
        match="rehearsal symbol cannot be a protected symbol",
    ):
        run_alpaca_paper_order_rehearsal(
            client=client,
            safety_check=_allowed_live_check(),
            symbol="aapl",
            reference_price=100,
            client_order_id="rehearsal-aapl-1",
            protected_positions={"AAPL": -1},
            confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
            order_output_dir=tmp_path / "orders",
            fill_output_dir=tmp_path / "fills",
            snapshot_output_dir=tmp_path / "snapshots",
            reconciliation_output_path=tmp_path / "reconciliation.json",
            rehearsal_output_dir=tmp_path / "rehearsals",
            max_order_notional=150,
            order_poll_interval_seconds=0,
        )

    assert client.fills() == ()
    assert not (tmp_path / "snapshots").exists()


def test_rehearsal_submits_one_buy_and_writes_complete_evidence(
    tmp_path,
) -> None:
    client = FakeLiveBrokerClient(
        initial_cash=1000,
        positions=(_position("AAPL", -1),),
    )

    result = run_alpaca_paper_order_rehearsal(
        client=client,
        safety_check=_allowed_live_check(),
        symbol="MSFT",
        reference_price=100,
        client_order_id="rehearsal-msft-1",
        protected_positions={"AAPL": -1},
        confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_path=tmp_path / "reconciliation.json",
        rehearsal_output_dir=tmp_path / "rehearsals",
        max_order_notional=150,
        order_poll_interval_seconds=0,
    )

    result_payload = json.loads(
        next((tmp_path / "rehearsals").glob("*.json")).read_text()
    )
    assert result.status == "passed"
    assert result.order_status == LiveOrderStatus.FILLED
    assert result.protected_positions_expected == {"AAPL": -1}
    assert result.protected_positions_before == {"AAPL": -1}
    assert result.protected_positions_after == {"AAPL": -1}
    assert result.asset_tradable is True
    assert result.rehearsal_symbol_quantity_before == 0
    assert result.rehearsal_symbol_quantity_after == 1
    assert result.reconciliation_passed is True
    assert len(list((tmp_path / "orders").glob("*.json"))) == 1
    assert len(list((tmp_path / "fills").glob("*.json"))) == 1
    assert len(list((tmp_path / "snapshots").glob("*.json"))) == 2
    assert result_payload["client_order_id"] == "rehearsal-msft-1"


def test_rehearsal_writes_failure_evidence_without_cleanup_when_rejected(
    tmp_path,
) -> None:
    client = RejectingLiveBrokerClient(
        initial_cash=1000,
        positions=(_position("AAPL", -1),),
    )

    result = run_alpaca_paper_order_rehearsal(
        client=client,
        safety_check=_allowed_live_check(),
        symbol="MSFT",
        reference_price=100,
        client_order_id="rehearsal-msft-1",
        protected_positions={"AAPL": -1},
        confirmation=ALPACA_PAPER_REHEARSAL_CONFIRMATION,
        order_output_dir=tmp_path / "orders",
        fill_output_dir=tmp_path / "fills",
        snapshot_output_dir=tmp_path / "snapshots",
        reconciliation_output_path=tmp_path / "reconciliation.json",
        rehearsal_output_dir=tmp_path / "rehearsals",
        max_order_notional=150,
        order_poll_interval_seconds=0,
    )

    assert result.status == "failed"
    assert result.order_status == LiveOrderStatus.REJECTED
    assert result.failure_reason is not None
    assert "order finished rejected instead of filled" in result.failure_reason
    assert "rehearsal symbol MSFT expected 1 but observed 0" in (
        result.failure_reason
    )
    assert client.submission_count == 1
    assert client.fills() == ()
    assert len(list((tmp_path / "rehearsals").glob("*.json"))) == 1


class RejectingLiveBrokerClient(FakeLiveBrokerClient):
    def __init__(self, **kwargs) -> None:
        super().__init__(**kwargs)
        self.submission_count = 0

    def submit_market_order(self, request, **kwargs) -> LiveOrderRecord:
        self.submission_count += 1
        record = super().submit_market_order(request, **kwargs)
        rejected = record.model_copy(
            update={
                "status": LiveOrderStatus.REJECTED,
                "rejection_reason": "simulated broker rejection",
            }
        )
        self._orders[record.client_order_id] = rejected
        self._fills.clear()
        self._cash += record.notional
        self._positions.pop(request.symbol, None)
        return rejected


def _position(symbol: str, quantity: int) -> Position:
    return Position(
        symbol=symbol,
        quantity=quantity,
        average_price=100,
        last_price=100,
    )


def _allowed_live_check() -> TradingSafetyCheck:
    return TradingSafetyCheck(mode=TradingMode.LIVE, allowed=True)
