"""Data ingestion with provider/normalizer separation."""

from pathlib import Path

from quant.data.normalizers import normalize_market_bars, raw_records_for_csv
from quant.data.providers.base import DataProvider
from quant.models.ingestion import IngestArtifactPaths, IngestRequest


def ingest_market_bars(
    provider: DataProvider,
    request: IngestRequest,
    raw_root: Path,
    normalized_root: Path,
) -> list[IngestArtifactPaths]:
    raw = provider.fetch(request)
    artifacts: list[IngestArtifactPaths] = []

    for symbol in request.symbols:
        raw_path = _market_bar_path(raw_root, raw.provider, symbol, request)
        normalized_path = normalized_root / "market_bars" / f"{symbol}.csv"

        raw_path.parent.mkdir(parents=True, exist_ok=True)
        normalized_path.parent.mkdir(parents=True, exist_ok=True)

        raw_records_for_csv(raw, symbol).to_csv(raw_path, index=False)
        normalized = normalize_market_bars(raw, symbol)
        normalized.frame.to_csv(normalized_path, index=False)

        artifacts.append(
            IngestArtifactPaths(
                raw_path=str(raw_path),
                normalized_path=str(normalized_path),
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
