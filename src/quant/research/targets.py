from datetime import datetime, timedelta
from decimal import Decimal

from quant.models.targets import (
    StrategyTargetDecision,
    StrategyTargetFrame,
    TargetDeclaredStatus,
    TargetEffectiveStatus,
    TargetUnit,
)


def evaluate_target_effective_status(
    decision: StrategyTargetDecision,
    *,
    evaluated_at: datetime,
    max_age: timedelta,
) -> TargetEffectiveStatus:
    if decision.declared_status == TargetDeclaredStatus.UNAVAILABLE:
        return TargetEffectiveStatus.UNAVAILABLE
    if evaluated_at < decision.effective_at:
        return TargetEffectiveStatus.NOT_YET_EFFECTIVE
    if evaluated_at > decision.valid_until:
        return TargetEffectiveStatus.EXPIRED
    if evaluated_at - decision.generated_at > max_age:
        return TargetEffectiveStatus.STALE
    return TargetEffectiveStatus.ACTIVE


def require_operational_whole_share_targets(
    frame: StrategyTargetFrame,
) -> StrategyTargetFrame:
    """Reject unsupported operational quantities without rounding."""
    if frame.unit != TargetUnit.SHARES:
        raise ValueError("operational target unit must be shares")
    fractional = [
        value
        for value in frame.targets
        if Decimal(value) != Decimal(value).to_integral_value()
    ]
    if fractional:
        raise ValueError("operational whole-share targets cannot be fractional")
    return frame
