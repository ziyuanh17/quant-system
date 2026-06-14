"""Test paper state behavior and safety invariants."""

import quant.execution.state
from quant.execution import (
    PaperBroker,
    load_paper_broker_state,
    save_paper_broker_state,
)
from quant.models.execution import (
    OrderRequest,
    OrderSide,
    PaperBrokerState,
    Position,
)


def test_load_paper_broker_state_uses_default_when_missing(tmp_path) -> None:
    state = load_paper_broker_state(
        tmp_path / "state.json",
        default_cash=1_000,
    )

    assert state.cash == 1_000
    assert state.positions == ()


def test_save_and_load_paper_broker_state_round_trips(tmp_path) -> None:
    broker = PaperBroker(initial_cash=1_000)
    broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=2),
        market_price=10,
    )
    path = tmp_path / "state.json"

    save_paper_broker_state(broker.state(), path)
    loaded = load_paper_broker_state(path, default_cash=0)

    assert loaded.cash == 980
    assert loaded.positions[0].symbol == "AAPL"
    assert loaded.positions[0].quantity == 2
    assert loaded.processed_signal_keys == ()


def test_paper_broker_can_resume_from_state() -> None:
    broker = PaperBroker.from_state(
        PaperBrokerState(
            cash=980,
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=2,
                    average_price=10,
                    last_price=10,
                ),
            ),
        )
    )

    assert broker.cash == 980
    assert broker.positions["AAPL"].quantity == 2


def test_paper_broker_state_preserves_processed_signal_keys() -> None:
    broker = PaperBroker.from_state(
        PaperBrokerState(
            cash=1_000,
            processed_signal_keys=("momentum:AAPL:2024-01-25:buy",),
        )
    )

    assert broker.has_processed_signal("momentum:AAPL:2024-01-25:buy")


def test_save_paper_broker_state_writes_backup_for_existing_state(
    tmp_path,
) -> None:
    path = tmp_path / "state.json"
    save_paper_broker_state(PaperBrokerState(cash=1_000), path)

    save_paper_broker_state(PaperBrokerState(cash=900), path)

    backup = path.with_name("state.json.bak")
    assert load_paper_broker_state(path, default_cash=0).cash == 900
    assert load_paper_broker_state(backup, default_cash=0).cash == 1_000


def test_failed_atomic_replace_keeps_previous_state(
    tmp_path,
    monkeypatch,
) -> None:
    path = tmp_path / "state.json"
    save_paper_broker_state(PaperBrokerState(cash=1_000), path)

    def fail_replace(source, destination) -> None:
        raise OSError("replace failed")

    monkeypatch.setattr(quant.execution.state.os, "replace", fail_replace)

    try:
        save_paper_broker_state(PaperBrokerState(cash=900), path)
    except OSError as exc:
        assert str(exc) == "replace failed"
    else:
        raise AssertionError("expected replace failure")

    assert load_paper_broker_state(path, default_cash=0).cash == 1_000
    assert list(tmp_path.glob(".*.tmp")) == []
