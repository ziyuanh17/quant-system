"""News and sentiment models."""

from datetime import datetime

from pydantic import HttpUrl

from quant.models.base import FrozenModel


class NewsArticle(FrozenModel):
    provider: str
    article_id: str
    published_at: datetime
    title: str
    body: str
    url: HttpUrl
    symbols: tuple[str, ...]
    source: str


class TextSentimentFeature(FrozenModel):
    source_id: str
    symbol: str
    timestamp: datetime
    sentiment_score: float
    model_name: str
