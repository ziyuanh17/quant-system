from pathlib import Path
from typing import Protocol

from quant.models.market import PriceData


class MarketBarStore(Protocol):
    def write(self, prices: PriceData) -> Path:
        ...

    def read(self, symbol: str) -> PriceData:
        ...

    def path_for(self, symbol: str) -> Path:
        ...
