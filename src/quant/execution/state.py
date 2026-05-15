from pathlib import Path

from quant.models.execution import PaperBrokerState, Position


def load_paper_broker_state(
    path: Path,
    *,
    default_cash: float,
    default_positions: tuple[Position, ...] = (),
) -> PaperBrokerState:
    """Load paper account state, or create an initial state when absent."""

    if path.exists():
        return PaperBrokerState.model_validate_json(path.read_text())
    return PaperBrokerState(
        cash=default_cash,
        positions=default_positions,
    )


def save_paper_broker_state(
    state: PaperBrokerState,
    path: Path,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(state.model_dump_json(indent=2) + "\n")
    return path
