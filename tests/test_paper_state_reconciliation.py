"""Test paper state reconciliation behavior and safety invariants."""

from typer.testing import CliRunner

from quant.cli import app
from quant.execution import (
    PaperBroker,
    reconcile_paper_state,
    save_paper_broker_state,
    write_paper_signal_record,
)
from quant.models.execution import (
    OrderRequest,
    OrderSide,
    PaperBrokerState,
    PaperSignalAction,
    PaperSignalDecision,
    PaperSignalRecord,
)


def test_reconcile_paper_state_passes_when_state_matches_audit_trail(
    tmp_path,
) -> None:
    state_path, signal_dir, state = _write_matching_state_and_signals(tmp_path)

    report = reconcile_paper_state(
        state=state,
        state_path=state_path,
        signal_records_dir=signal_dir,
        initial_cash=1_000,
    )

    assert report.passed
    assert report.signal_record_count == 2
    assert report.filled_trade_count == 2
    assert report.expected_cash == 992
    assert report.actual_cash == 992
    assert report.differences == ()


def test_reconcile_paper_state_reports_cash_difference(tmp_path) -> None:
    state_path, signal_dir, state = _write_matching_state_and_signals(tmp_path)
    drifted_state = PaperBrokerState(
        cash=state.cash + 1,
        positions=state.positions,
        processed_signal_keys=state.processed_signal_keys,
    )

    report = reconcile_paper_state(
        state=drifted_state,
        state_path=state_path,
        signal_records_dir=signal_dir,
        initial_cash=1_000,
    )

    assert not report.passed
    assert report.differences[0].field == "cash"


def test_reconcile_paper_state_cli_writes_report(tmp_path) -> None:
    state_path, signal_dir, _state = _write_matching_state_and_signals(tmp_path)
    report_path = tmp_path / "reports" / "state.json"

    result = CliRunner().invoke(
        app,
        [
            "paper",
            "reconcile-state",
            "--state-path",
            str(state_path),
            "--signal-records-dir",
            str(signal_dir),
            "--initial-cash",
            "1000",
            "--output-path",
            str(report_path),
        ],
    )

    assert result.exit_code == 0
    assert "Status: passed" in result.output
    assert "Differences: 0" in result.output
    assert report_path.exists()


def test_reconcile_paper_state_cli_exits_nonzero_for_drift(tmp_path) -> None:
    state_path, signal_dir, state = _write_matching_state_and_signals(tmp_path)
    save_paper_broker_state(
        PaperBrokerState(
            cash=state.cash + 1,
            positions=state.positions,
            processed_signal_keys=state.processed_signal_keys,
        ),
        state_path,
    )

    result = CliRunner().invoke(
        app,
        [
            "paper",
            "reconcile-state",
            "--state-path",
            str(state_path),
            "--signal-records-dir",
            str(signal_dir),
            "--initial-cash",
            "1000",
            "--output-path",
            str(tmp_path / "reports" / "state.json"),
        ],
    )

    assert result.exit_code == 1
    assert "Status: failed" in result.output
    assert "[difference] cash" in result.output


def _write_matching_state_and_signals(tmp_path):
    signal_dir = tmp_path / "signals"
    state_path = tmp_path / "state" / "paper.json"
    broker = PaperBroker(initial_cash=1_000)

    buy_record = _execute_signal(
        broker=broker,
        action=PaperSignalAction.BUY,
        signal_date="2024-01-25",
        price=10,
        quantity=2,
    )
    sell_record = _execute_signal(
        broker=broker,
        action=PaperSignalAction.SELL,
        signal_date="2024-01-26",
        price=12,
        quantity=1,
    )

    write_paper_signal_record(buy_record, signal_dir)
    write_paper_signal_record(sell_record, signal_dir)
    state = broker.state()
    save_paper_broker_state(state, state_path)
    return state_path, signal_dir, state


def _execute_signal(
    *,
    broker: PaperBroker,
    action: PaperSignalAction,
    signal_date: str,
    price: float,
    quantity: int,
) -> PaperSignalRecord:
    side = OrderSide.BUY if action == PaperSignalAction.BUY else OrderSide.SELL
    trade = broker.submit_market_order(
        OrderRequest(symbol="AAPL", side=side, quantity=quantity),
        market_price=price,
    )
    key = f"momentum:AAPL:{signal_date}:{action.value}"
    broker.mark_signal_processed(key)
    return PaperSignalRecord(
        decision=PaperSignalDecision(
            symbol="AAPL",
            action=action,
            signal_date=signal_date,
            market_price=price,
            reason="test signal",
            idempotency_key=key,
        ),
        trade=trade,
        snapshot=trade.snapshot,
    )
