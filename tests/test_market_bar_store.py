import pandas as pd

from quant.data.stores import CsvMarketBarStore
from quant.models.market import PriceData


def test_csv_market_bar_store_writes_and_reads_prices(tmp_path) -> None:
    store = CsvMarketBarStore(tmp_path)
    prices = PriceData(symbol="AAPL", frame=_price_frame())

    path = store.write(prices)
    loaded = store.read("AAPL")

    assert path == tmp_path / "market_bars" / "AAPL.csv"
    assert path.exists()
    assert loaded.symbol == "AAPL"
    assert loaded.frame["close"].tolist() == [104.0, 105.0]


def test_csv_market_bar_store_path_for_symbol(tmp_path) -> None:
    store = CsvMarketBarStore(tmp_path)

    assert store.path_for("MSFT") == tmp_path / "market_bars" / "MSFT.csv"


def _price_frame() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": ["2024-01-02", "2024-01-03"],
            "symbol": ["AAPL", "AAPL"],
            "open": [100.0, 101.0],
            "high": [105.0, 106.0],
            "low": [99.0, 100.0],
            "close": [104.0, 105.0],
            "volume": [1000, 1200],
            "adjusted_close": [104.0, 105.0],
            "provider": ["test", "test"],
        }
    )
