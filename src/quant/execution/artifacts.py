from pathlib import Path
from uuid import uuid4

from quant.models.execution import (
    DryRunOrderRecord,
    PaperSignalRecord,
    PaperTradeRecord,
)


def write_paper_trade_record(
    record: PaperTradeRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.order.id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def write_paper_signal_record(
    record: PaperSignalRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.decision.signal_date}-{uuid4()}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def write_dry_run_order_record(
    record: DryRunOrderRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path
