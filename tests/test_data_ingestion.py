import json

import pandas as pd

from quant.data.ingest import ingest_market_bars
from quant.data.normalizers import normalize_market_bars
from quant.data.providers.yfinance_provider import _frame_to_records
from quant.data.stores import CsvMarketBarStore
from quant.models.ingestion import DataModality, IngestRequest, RawDataset


def test_normalize_market_bars_converts_yfinance_shape() -> None:
    request = IngestRequest(symbols=("AAPL",), start="2024-01-01")
    raw = RawDataset(
        provider="test",
        modality=DataModality.MARKET_BARS,
        request=request,
        records=[
            {
                "Date": "2024-01-02",
                "symbol": "AAPL",
                "Open": 100.0,
                "High": 110.0,
                "Low": 99.0,
                "Close": 105.0,
                "Adj Close": 104.5,
                "Volume": 1000,
            }
        ],
    )

    prices = normalize_market_bars(raw, "AAPL")

    assert prices.symbol == "AAPL"
    assert list(prices.frame.columns) == [
        "date",
        "symbol",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted_close",
        "provider",
    ]
    assert prices.frame.loc[0, "close"] == 105.0


def test_ingest_market_bars_writes_raw_and_normalized_files(tmp_path) -> None:
    request = IngestRequest(symbols=("AAPL",), start="2024-01-01")
    provider = FakeMarketBarProvider()

    artifacts = ingest_market_bars(
        provider,
        request,
        raw_root=tmp_path / "raw",
        normalized_root=tmp_path / "normalized",
        validation_root=tmp_path / "validation",
        metadata_root=tmp_path / "metadata",
    )

    assert len(artifacts) == 1
    assert (tmp_path / "normalized" / "market_bars" / "AAPL.csv").exists()
    assert (tmp_path / "validation" / "market_bars" / "AAPL.json").exists()
    assert (tmp_path / "metadata" / "market_bars" / "AAPL.json").exists()
    assert "provider=fake" in artifacts[0].raw_path
    assert "modality=market_bars" in artifacts[0].raw_path
    assert artifacts[0].validation_passed is True

    metadata = json.loads(
        (tmp_path / "metadata" / "market_bars" / "AAPL.json").read_text()
    )
    assert metadata["provider"] == "fake"
    assert metadata["modality"] == "market_bars"
    assert metadata["symbol"] == "AAPL"
    assert metadata["validation_status"] == "passed"
    assert metadata["normalization_version"] == "market_bars.v1"
    assert metadata["raw_path"] == artifacts[0].raw_path
    assert metadata["normalized_path"] == artifacts[0].normalized_path

    report = json.loads(
        (tmp_path / "validation" / "market_bars" / "AAPL.json").read_text()
    )
    assert report["passed"] is True
    assert report["issues"] == []


def test_ingest_market_bars_accepts_market_bar_store(tmp_path) -> None:
    request = IngestRequest(symbols=("AAPL",), start="2024-01-01")
    provider = FakeMarketBarProvider()
    store = CsvMarketBarStore(tmp_path / "custom")

    artifacts = ingest_market_bars(
        provider,
        request,
        raw_root=tmp_path / "raw",
        normalized_root=tmp_path / "unused",
        store=store,
    )

    assert artifacts[0].normalized_path == str(
        tmp_path / "custom" / "market_bars" / "AAPL.csv"
    )
    assert store.read("AAPL").frame["close"].tolist() == [105.0]


def test_ingest_market_bars_records_failed_validation(tmp_path) -> None:
    request = IngestRequest(symbols=("AAPL",), start="2024-01-01")
    provider = BadMarketBarProvider()

    artifacts = ingest_market_bars(
        provider,
        request,
        raw_root=tmp_path / "raw",
        normalized_root=tmp_path / "normalized",
        validation_root=tmp_path / "validation",
        metadata_root=tmp_path / "metadata",
    )

    metadata = json.loads(
        (tmp_path / "metadata" / "market_bars" / "AAPL.json").read_text()
    )

    assert artifacts[0].validation_passed is False
    assert metadata["validation_status"] == "failed"
    assert metadata["validation_issue_count"] > 0


def test_yfinance_records_flatten_multiindex_columns() -> None:
    frame = pd.DataFrame(
        [[100.0, 105.0]],
        columns=pd.MultiIndex.from_tuples(
            [("Open", "AAPL"), ("Close", "AAPL")]
        ),
        index=pd.to_datetime(["2024-01-02"]),
    )
    frame.index.name = "Date"

    records = _frame_to_records(frame, "AAPL")

    assert records[0]["Open"] == 100.0
    assert records[0]["Close"] == 105.0
    assert records[0]["symbol"] == "AAPL"


class FakeMarketBarProvider:
    name = "fake"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=[
                {
                    "Date": "2024-01-02",
                    "symbol": "AAPL",
                    "Open": 100.0,
                    "High": 110.0,
                    "Low": 99.0,
                    "Close": 105.0,
                    "Adj Close": 104.5,
                    "Volume": 1000,
                }
            ],
        )


class BadMarketBarProvider:
    name = "bad"
    modality = DataModality.MARKET_BARS

    def fetch(self, request: IngestRequest) -> RawDataset:
        return RawDataset(
            provider=self.name,
            modality=self.modality,
            request=request,
            records=[
                {
                    "Date": "2024-01-02",
                    "symbol": "AAPL",
                    "Open": 100.0,
                    "High": 99.0,
                    "Low": 100.0,
                    "Close": 101.0,
                    "Adj Close": 101.0,
                    "Volume": 1000,
                }
            ],
        )
