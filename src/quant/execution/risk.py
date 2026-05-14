from quant.models.execution import (
    OrderRequest,
    OrderSide,
    Position,
    RiskCheckResult,
    RiskDecision,
)


def check_order_risk(
    request: OrderRequest,
    *,
    cash: float,
    positions: dict[str, Position],
    market_price: float,
) -> RiskCheckResult:
    """Run first-pass paper-trading risk checks.

    This is intentionally small: enough to prevent impossible paper fills while
    leaving room for richer limits such as max position size or daily loss caps.
    """

    if market_price <= 0:
        return RiskCheckResult(
            decision=RiskDecision.REJECTED,
            reason="market price must be positive",
        )

    notional = request.quantity * market_price
    if request.side == OrderSide.BUY and notional > cash:
        return RiskCheckResult(
            decision=RiskDecision.REJECTED,
            reason="insufficient cash",
        )

    current_position = positions.get(request.symbol)
    current_quantity = (
        0 if current_position is None else current_position.quantity
    )
    if request.side == OrderSide.SELL and request.quantity > current_quantity:
        return RiskCheckResult(
            decision=RiskDecision.REJECTED,
            reason="insufficient position quantity",
        )

    return RiskCheckResult(decision=RiskDecision.APPROVED)
