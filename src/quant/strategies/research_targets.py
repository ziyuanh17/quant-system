"""Implement research-only strategies that emit signed target positions."""

from decimal import Decimal

import pandas as pd
from pydantic import Field, model_validator

from quant.models.base import FrozenModel
from quant.models.market import PriceData
from quant.models.targets import StrategyTargetFrame, TargetUnit


class TargetNativeTrendConfig(FrozenModel):
    """Parameters for signed moving-average trend targets."""

    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)
    long_target_shares: Decimal = Decimal("1")
    short_target_shares: Decimal = Decimal("-1")

    @model_validator(mode="after")
    def validate_windows_and_target_signs(self) -> "TargetNativeTrendConfig":
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if self.long_target_shares <= 0:
            raise ValueError("long_target_shares must be positive")
        if self.short_target_shares >= 0:
            raise ValueError("short_target_shares must be negative")
        return self


class TargetNativeTrendStrategy:
    """Trend-following strategy expressed directly as signed share targets."""

    name = "target-native-trend"

    def __init__(self, config: TargetNativeTrendConfig | None = None) -> None:
        self.config = config or TargetNativeTrendConfig()

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame:
        close = prices.close
        fast = close.rolling(self.config.fast_window).mean()
        slow = close.rolling(self.config.slow_window).mean()

        targets = pd.Series(Decimal("0"), index=close.index, dtype=object)
        targets.loc[fast > slow] = self.config.long_target_shares
        targets.loc[fast < slow] = self.config.short_target_shares
        return StrategyTargetFrame(unit=TargetUnit.SHARES, targets=targets)


class DeclaredNotionalTrendConfig(FrozenModel):
    """Parameters for trend targets sized by strategy-declared notional."""

    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)
    long_target_notional: Decimal = Decimal("100000")
    short_target_notional: Decimal = Decimal("-100000")

    @model_validator(mode="after")
    def validate_declared_notional_config(
        self,
    ) -> "DeclaredNotionalTrendConfig":
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if self.long_target_notional <= 0:
            raise ValueError("long_target_notional must be positive")
        if self.short_target_notional >= 0:
            raise ValueError("short_target_notional must be negative")
        return self


class DeclaredNotionalTrendStrategy:
    """Trend strategy whose sizing policy is declared target notional."""

    name = "declared-notional-trend"

    def __init__(
        self, config: DeclaredNotionalTrendConfig | None = None
    ) -> None:
        self.config = config or DeclaredNotionalTrendConfig()

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame:
        close = prices.close
        fast = close.rolling(self.config.fast_window).mean()
        slow = close.rolling(self.config.slow_window).mean()

        targets: list[Decimal] = []
        for price, fast_value, slow_value in zip(
            close, fast, slow, strict=True
        ):
            if pd.isna(price):
                targets.append(Decimal("0"))
                continue
            price_decimal = Decimal(str(price))
            if price_decimal <= 0:
                targets.append(Decimal("0"))
            elif fast_value > slow_value:
                targets.append(
                    self.config.long_target_notional / price_decimal
                )
            elif fast_value < slow_value:
                targets.append(
                    self.config.short_target_notional / price_decimal
                )
            else:
                targets.append(Decimal("0"))

        return StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(targets, index=close.index, dtype=object),
        )


class VolatilityAdjustedTrendConfig(FrozenModel):
    """Parameters for volatility-scaled trend targets."""

    fast_window: int = Field(default=5, ge=2)
    slow_window: int = Field(default=20, ge=3)
    volatility_window: int = Field(default=20, ge=2)
    base_target_shares: Decimal = Decimal("1.0")
    min_target_shares: Decimal = Decimal("0.25")
    max_target_shares: Decimal = Decimal("1.0")

    @model_validator(mode="after")
    def validate_volatility_target_config(
        self,
    ) -> "VolatilityAdjustedTrendConfig":
        if self.fast_window >= self.slow_window:
            raise ValueError("fast_window must be smaller than slow_window")
        if self.base_target_shares <= 0:
            raise ValueError("base_target_shares must be positive")
        if self.min_target_shares <= 0:
            raise ValueError("min_target_shares must be positive")
        if self.max_target_shares < self.min_target_shares:
            raise ValueError("max_target_shares must be at least min target")
        return self


class VolatilityAdjustedTrendStrategy:
    """Trend strategy that scales research exposure by recent volatility."""

    name = "volatility-adjusted-target-trend"

    def __init__(
        self, config: VolatilityAdjustedTrendConfig | None = None
    ) -> None:
        self.config = config or VolatilityAdjustedTrendConfig()

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame:
        close = prices.close
        fast = close.rolling(self.config.fast_window).mean()
        slow = close.rolling(self.config.slow_window).mean()
        volatility = close.pct_change().rolling(
            self.config.volatility_window
        ).std()
        reference_volatility = volatility.rolling(
            self.config.volatility_window
        ).median()
        raw_scale = (
            float(self.config.base_target_shares)
            * reference_volatility
            / volatility
        )
        scale = raw_scale.clip(
            lower=float(self.config.min_target_shares),
            upper=float(self.config.max_target_shares),
        ).fillna(0.0)

        signed = pd.Series(0.0, index=close.index)
        signed.loc[fast > slow] = scale.loc[fast > slow]
        signed.loc[fast < slow] = -scale.loc[fast < slow]
        return _target_frame_from_float_series(signed)


class MeanReversionCounterweightConfig(FrozenModel):
    """Parameters for moving-average distance mean-reversion targets."""

    lookback_window: int = Field(default=20, ge=2)
    entry_zscore: Decimal = Decimal("1.5")
    exit_zscore: Decimal = Decimal("0.25")
    target_shares: Decimal = Decimal("1")

    @model_validator(mode="after")
    def validate_mean_reversion_config(
        self,
    ) -> "MeanReversionCounterweightConfig":
        if self.entry_zscore <= 0:
            raise ValueError("entry_zscore must be positive")
        if self.exit_zscore < 0 or self.exit_zscore >= self.entry_zscore:
            raise ValueError("exit_zscore must be non-negative and below entry")
        if self.target_shares <= 0:
            raise ValueError("target_shares must be positive")
        return self


class MeanReversionCounterweightStrategy:
    """Mean-reversion strategy expressed as signed share targets."""

    name = "mean-reversion-counterweight"

    def __init__(
        self, config: MeanReversionCounterweightConfig | None = None
    ) -> None:
        self.config = config or MeanReversionCounterweightConfig()

    def generate_targets(self, prices: PriceData) -> StrategyTargetFrame:
        close = prices.close
        average = close.rolling(self.config.lookback_window).mean()
        deviation = close.rolling(self.config.lookback_window).std()
        zscore = (close - average) / deviation

        current = Decimal("0")
        values: list[Decimal] = []
        entry = float(self.config.entry_zscore)
        exit_ = float(self.config.exit_zscore)
        for value in zscore:
            if pd.isna(value):
                current = Decimal("0")
            elif value >= entry:
                current = -self.config.target_shares
            elif value <= -entry:
                current = self.config.target_shares
            elif abs(float(value)) <= exit_:
                current = Decimal("0")
            values.append(current)

        return StrategyTargetFrame(
            unit=TargetUnit.SHARES,
            targets=pd.Series(values, index=close.index, dtype=object),
        )


def _target_frame_from_float_series(values: pd.Series) -> StrategyTargetFrame:
    return StrategyTargetFrame(
        unit=TargetUnit.SHARES,
        targets=pd.Series(
            [Decimal(str(round(float(value), 8))) for value in values],
            index=values.index,
            dtype=object,
        ),
    )
