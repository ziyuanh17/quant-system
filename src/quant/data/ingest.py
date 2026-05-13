"""Data ingestion with provider/normalizer separation."""

from pathlib import Path

from quant.data.lineage import write_dataset_metadata, write_validation_report
from quant.data.normalizers import (
    MARKET_BAR_NORMALIZATION_VERSION,
    normalize_market_bars,
    raw_records_for_csv,
)
from quant.data.providers.base import DataProvider
from quant.data.validation import validate_market_bars_csv
from quant.models.ingestion import (
    DatasetMetadata,
    IngestArtifactPaths,
    IngestRequest,
)


def ingest_market_bars(
    provider: DataProvider,
    request: IngestRequest,
    raw_root: Path,
    normalized_root: Path,
    validation_root: Path | None = None,
    metadata_root: Path | None = None,
    validate: bool = True,
    min_rows: int = 1,
) -> list[IngestArtifactPaths]:
    raw = provider.fetch(request)
    artifacts: list[IngestArtifactPaths] = []

    for symbol in request.symbols:
        raw_path = _market_bar_path(raw_root, raw.provider, symbol, request)
        normalized_path = normalized_root / "market_bars" / f"{symbol}.csv"
        validation_report_path = (
            _lineage_path(validation_root, "market_bars", symbol)
            if validation_root is not None
            else None
        )
        metadata_path = (
            _lineage_path(metadata_root, "market_bars", symbol)
            if metadata_root is not None
            else None
        )

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.parent.mkdir(parents=True, exist_ok=True)

        raw_records_for_csv(raw, symbol).to_csv(raw_path, index=False)
        normalized = normalize_market_bars(raw, symbol)
        normalized.frame.to_csv(normalized_path, index=False)

        validation_passed: bool | None = None
        validation_issue_count: int | None = None
        if validate:
            report = validate_market_bars_csv(
                normalized_path, symbol, min_rows=min_rows
            )
            validation_passed = report.passed
            validation_issue_count = report.issue_count
            if validation_report_path is not None:
                write_validation_report(report, validation_report_path)

        if metadata_path is not None:
            metadata = DatasetMetadata(
                provider=raw.provider,
                modality=raw.modality,
                symbol=symbol,
                request_start=request.start,
                request_end=request.end,
                raw_path=str(raw_path),
                normalized_path=str(normalized_path),
                validation_report_path=(
                    str(validation_report_path)
                    if validation_report_path is not None
                    else None
                ),
                ingested_at=raw.fetched_at,
                normalization_version=MARKET_BAR_NORMALIZATION_VERSION,
                validation_status=_validation_status(validation_passed),
                validation_issue_count=validation_issue_count,
            )
            write_dataset_metadata(metadata, metadata_path)

        artifacts.append(
            IngestArtifactPaths(
                raw_path=str(raw_path),
                normalized_path=str(normalized_path),
                validation_report_path=(
                    str(validation_report_path)
                    if validation_report_path is not None
                    else None
                ),
                metadata_path=str(metadata_path) if metadata_path else None,
                validation_passed=validation_passed,
            )
        )

    return artifacts


def _market_bar_path(
    raw_root: Path,
    provider: str,
    symbol: str,
    request: IngestRequest,
) -> Path:
    end = request.end or "latest"
    return (
        raw_root
        / f"provider={provider}"
        / "modality=market_bars"
        / f"symbol={symbol}"
        / f"start={request.start}_end={end}.csv"
    )


def _lineage_path(root: Path | None, modality: str, symbol: str) -> Path | None:
    if root is None:
        return None
    return root / modality / f"{symbol}.json"


def _validation_status(validation_passed: bool | None) -> str:
    if validation_passed is None:
        return "skipped"
    if validation_passed:
        return "passed"
    return "failed"
