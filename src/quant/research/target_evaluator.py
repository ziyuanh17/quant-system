"""Evaluate native target strategies and sizing policies."""

from decimal import Decimal
from typing import Protocol, TypeVar

import pandas as pd

from quant.models.features import FeatureData
from quant.models.market import PriceData
from quant.models.signals import SignalFrame
from quant.models.targets import (
    StrategyTargetFrame,
    TargetSimulationInput,
    TargetUnit,
)
from quant.strategies.base import (
    FeatureStrategy,
    FeatureTargetStrategy,
    Strategy,
    TargetStrategy,
)

ResearchTargetDataT = TypeVar("ResearchTargetDataT", contravariant=True)


class TargetSimulationAdapter(Protocol[ResearchTargetDataT]):
    def build(self, data: ResearchTargetDataT) -> TargetSimulationInput: ...


class PriceTargetStrategySimulationAdapter:
    def __init__(self, strategy: TargetStrategy) -> None:
        self._strategy = strategy

    def build(self, data: PriceData) -> TargetSimulationInput:
        return TargetSimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            targets=self._strategy.generate_targets(data),
        )


class FeatureTargetStrategySimulationAdapter:
    def __init__(self, strategy: FeatureTargetStrategy) -> None:
        self._strategy = strategy

    def build(self, data: FeatureData) -> TargetSimulationInput:
        return TargetSimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            targets=self._strategy.generate_targets_from_features(data),
        )


class FixedSharesLegacyPriceAdapter:
    sizing_policy_version = "fixed_shares_v1"

    def __init__(self, strategy: Strategy, *, shares: Decimal) -> None:
        if shares <= 0:
            raise ValueError("fixed shares must be positive")
        self._strategy = strategy
        self._shares = shares

    def build(self, data: PriceData) -> TargetSimulationInput:
        return TargetSimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            targets=signals_to_fixed_share_targets(
                self._strategy.generate_signals(data), shares=self._shares
            ),
            diagnostics=(f"sizing_policy={self.sizing_policy_version}",),
        )


class FixedSharesLegacyFeatureAdapter:
    sizing_policy_version = "fixed_shares_v1"

    def __init__(self, strategy: FeatureStrategy, *, shares: Decimal) -> None:
        if shares <= 0:
            raise ValueError("fixed shares must be positive")
        self._strategy = strategy
        self._shares = shares

    def build(self, data: FeatureData) -> TargetSimulationInput:
        return TargetSimulationInput(
            strategy_name=self._strategy.name,
            symbol=data.symbol,
            close=data.close,
            targets=signals_to_fixed_share_targets(
                self._strategy.generate_signals_from_features(data),
                shares=self._shares,
            ),
            diagnostics=(f"sizing_policy={self.sizing_policy_version}",),
        )


def signals_to_fixed_share_targets(
    signals: SignalFrame,
    *,
    shares: Decimal,
) -> StrategyTargetFrame:
    targets: list[Decimal] = []
    current = Decimal("0")
    for entry, exit_ in zip(signals.entries, signals.exits, strict=True):
        if bool(entry) and bool(exit_):
            raise ValueError("entry and exit cannot both be true on one row")
        if bool(entry):
            current = shares
        elif bool(exit_):
            current = Decimal("0")
        targets.append(current)
    return StrategyTargetFrame(
        unit=TargetUnit.SHARES,
        targets=pd.Series(targets, index=signals.entries.index, dtype=object),
    )
