"""Evaluate strategy candidates under research policies."""

from typing import Protocol, TypeVar

from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.research import StrategySimulationInput
from quant.strategies.base import FeatureStrategy, Strategy

ResearchDataT = TypeVar("ResearchDataT", contravariant=True)


class StrategySimulationAdapter(Protocol[ResearchDataT]):
    """Normalize a strategy family into the shared simulation-input shape."""

    def build(self, data: ResearchDataT) -> StrategySimulationInput:
        ...


class PriceStrategySimulationAdapter:
    """Adapter for existing strategies that generate signals from prices."""

    def __init__(self, strategy: Strategy) -> None:
        self._strategy = strategy

    def build(self, data: PriceData) -> StrategySimulationInput:
        return StrategySimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            signals=self._strategy.generate_signals(data),
        )


class FeatureStrategySimulationAdapter:
    """Adapter for existing strategies that generate signals from features."""

    def __init__(self, strategy: FeatureStrategy) -> None:
        self._strategy = strategy

    def build(self, data: FeatureData) -> StrategySimulationInput:
        return StrategySimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            signals=self._strategy.generate_signals_from_features(data),
        )
