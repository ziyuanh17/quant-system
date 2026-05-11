import pandas as pd

from quant.data.ingest import ingest_market_bars
from quant.data.normalizers import normalize_market_bars
from quant.data.providers.yfinance_provider import _frame_to_records
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
    )

    assert len(artifacts) == 1
    assert (tmp_path / "normalized" / "market_bars" / "AAPL.csv").exists()
    assert "provider=fake" in artifacts[0].raw_path
    assert "modality=market_bars" in artifacts[0].raw_path


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
