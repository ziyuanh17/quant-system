"""Base interface for data providers."""

from typing import Protocol

from quant.models.ingestion import DataModality, IngestRequest, RawDataset


class DataProvider(Protocol):
    name: str
    modality: DataModality

    def fetch(self, request: IngestRequest) -> RawDataset: ...
