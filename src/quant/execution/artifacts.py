"""Persist execution order, fill, and snapshot artifacts."""

from pathlib import Path
from uuid import uuid4

from quant.models.execution import (
    DryRunOrderRecord,
    LiveAccountSnapshot,
    LiveFillRecord,
    LiveOrderRecord,
    LiveReconciliationReport,
    LiveRehearsalResult,
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


def write_live_order_record(
    record: LiveOrderRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def write_live_fill_record(
    record: LiveFillRecord,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{record.id}.json"
    path.write_text(record.model_dump_json(indent=2) + "\n")
    return path


def write_live_account_snapshot(
    snapshot: LiveAccountSnapshot,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{snapshot.id}.json"
    path.write_text(snapshot.model_dump_json(indent=2) + "\n")
    return path


def write_live_reconciliation_report(
    report: LiveReconciliationReport,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2) + "\n")
    return output_path


def write_live_rehearsal_result(
    result: LiveRehearsalResult,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{result.id}.json"
    path.write_text(result.model_dump_json(indent=2) + "\n")
    return path
