"""Store and retrieve market bars using CSV artifacts."""

from pathlib import Path

from quant.data.csv_loader import load_price_csv
from quant.models.market import PriceData


class CsvMarketBarStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def write(self, prices: PriceData) -> Path:
        path = self.path_for(prices.symbol)
        path.parent.mkdir(parents=True, exist_ok=True)
        prices.frame.to_csv(path, index=False)
        return path

    def read(self, symbol: str) -> PriceData:
        return load_price_csv(self.path_for(symbol), symbol)

    def path_for(self, symbol: str) -> Path:
        return self.root / "market_bars" / f"{symbol}.csv"
