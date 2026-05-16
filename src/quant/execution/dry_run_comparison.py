from pathlib import Path

from quant.models.execution import (
    DryRunOrderRecord,
    OrderSide,
    PaperDryRunComparisonReport,
    PaperDryRunComparisonStatus,
    PaperDryRunDifference,
    PaperSignalAction,
    PaperSignalRecord,
)


def compare_paper_signal_to_dry_run_order(
    *,
    paper_signal_path: Path,
    dry_run_order_path: Path | None,
    tolerance: float = 0.01,
) -> PaperDryRunComparisonReport:
    """Compare one paper signal artifact with one dry-run order artifact."""
    if tolerance < 0:
        raise ValueError("tolerance must be non-negative")

    paper = PaperSignalRecord.model_validate_json(
        paper_signal_path.read_text()
    )
    dry_run = (
        DryRunOrderRecord.model_validate_json(dry_run_order_path.read_text())
        if dry_run_order_path is not None
        else None
    )
    differences = _compare_records(
        paper=paper,
        dry_run=dry_run,
        tolerance=tolerance,
    )
    return PaperDryRunComparisonReport(
        paper_signal_path=str(paper_signal_path),
        dry_run_order_path=(
            str(dry_run_order_path) if dry_run_order_path is not None else None
        ),
        status=(
            PaperDryRunComparisonStatus.PASSED
            if not differences
            else PaperDryRunComparisonStatus.FAILED
        ),
        paper_action=paper.decision.action,
        dry_run_side=dry_run.request.side if dry_run is not None else None,
        paper_symbol=paper.decision.symbol,
        dry_run_symbol=(
            dry_run.request.symbol if dry_run is not None else None
        ),
        paper_quantity=_paper_quantity(paper),
        dry_run_quantity=(
            dry_run.request.quantity if dry_run is not None else None
        ),
        paper_market_price=paper.decision.market_price,
        dry_run_market_price=(
            dry_run.market_price if dry_run is not None else None
        ),
        paper_signal_date=paper.decision.signal_date,
        difference_tolerance=tolerance,
        difference_count=len(differences),
        differences=tuple(differences),
    )


def latest_json(path: Path) -> Path | None:
    files = sorted(
        path.glob("*.json"),
        key=lambda item: item.stat().st_mtime,
    )
    return files[-1] if files else None


def write_paper_dry_run_comparison_report(
    report: PaperDryRunComparisonReport,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2) + "\n")
    return output_path


def _compare_records(
    *,
    paper: PaperSignalRecord,
    dry_run: DryRunOrderRecord | None,
    tolerance: float,
) -> list[PaperDryRunDifference]:
    differences: list[PaperDryRunDifference] = []
    expected_side = _expected_side(paper)
    if expected_side is None:
        if dry_run is not None:
            differences.append(
                _difference(
                    "order_presence",
                    "none",
                    dry_run.status.value,
                    "paper signal is hold/skipped but dry-run order exists",
                )
            )
        return differences

    if dry_run is None:
        differences.append(
            _difference(
                "order_presence",
                "order",
                "none",
                "paper signal has an actionable order but dry-run is missing",
            )
        )
        return differences

    if expected_side != dry_run.request.side:
        differences.append(
            _difference(
                "side",
                expected_side.value,
                dry_run.request.side.value,
                "paper action and dry-run side do not match",
            )
        )
    if paper.decision.symbol != dry_run.request.symbol:
        differences.append(
            _difference(
                "symbol",
                paper.decision.symbol,
                dry_run.request.symbol,
                "paper symbol and dry-run symbol do not match",
            )
        )
    paper_quantity = _paper_quantity(paper)
    if paper_quantity != dry_run.request.quantity:
        differences.append(
            _difference(
                "quantity",
                str(paper_quantity),
                str(dry_run.request.quantity),
                "paper fill quantity and dry-run quantity do not match",
            )
        )
    if abs(paper.decision.market_price - dry_run.market_price) > tolerance:
        differences.append(
            _difference(
                "market_price",
                f"{paper.decision.market_price:.6f}",
                f"{dry_run.market_price:.6f}",
                "paper market price and dry-run market price do not match",
            )
        )
    return differences


def _expected_side(record: PaperSignalRecord) -> OrderSide | None:
    if record.skipped or record.decision.action == PaperSignalAction.HOLD:
        return None
    if record.decision.action == PaperSignalAction.BUY:
        return OrderSide.BUY
    return OrderSide.SELL


def _paper_quantity(record: PaperSignalRecord) -> int | None:
    if record.trade is None or record.trade.fill is None:
        return None
    return record.trade.fill.quantity


def _difference(
    field: str,
    paper_value: str,
    dry_run_value: str,
    message: str,
) -> PaperDryRunDifference:
    return PaperDryRunDifference(
        field=field,
        paper_value=paper_value,
        dry_run_value=dry_run_value,
        message=message,
    )
