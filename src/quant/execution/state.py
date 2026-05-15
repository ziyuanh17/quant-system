import os
from pathlib import Path
from shutil import copy2
from uuid import uuid4

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
    *,
    write_backup: bool = True,
) -> Path:
    """Persist paper account state with an atomic same-directory replace."""

    path.parent.mkdir(parents=True, exist_ok=True)
    if write_backup and path.exists():
        copy2(path, _backup_path(path))

    temp_path = _temp_state_path(path)
    try:
        _write_and_sync(temp_path, state.model_dump_json(indent=2) + "\n")
        os.replace(temp_path, path)
        _sync_directory(path.parent)
    finally:
        temp_path.unlink(missing_ok=True)

    return path


def _backup_path(path: Path) -> Path:
    return path.with_name(f"{path.name}.bak")


def _temp_state_path(path: Path) -> Path:
    return path.with_name(f".{path.name}.{uuid4()}.tmp")


def _write_and_sync(path: Path, payload: str) -> None:
    with path.open("w") as file:
        file.write(payload)
        file.flush()
        os.fsync(file.fileno())


def _sync_directory(path: Path) -> None:
    try:
        fd = os.open(path, os.O_RDONLY)
    except OSError:
        return

    try:
        os.fsync(fd)
    finally:
        os.close(fd)
