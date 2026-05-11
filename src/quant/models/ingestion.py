from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from quant.models.base import FrozenModel


class DataModality(StrEnum):
    MARKET_BARS = "market_bars"
    NEWS_ARTICLE = "news_article"
    FILING = "filing"
    SOCIAL_POST = "social_post"


class IngestRequest(FrozenModel):
    symbols: tuple[str, ...]
    start: str
    end: str | None = None


class RawDataset(FrozenModel):
    provider: str
    modality: DataModality
    request: IngestRequest
    fetched_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    records: list[dict[str, Any]]


class IngestArtifactPaths(FrozenModel):
    raw_path: str
    normalized_path: str
