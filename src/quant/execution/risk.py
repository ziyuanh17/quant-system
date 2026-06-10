from quant.models.execution import (
    AssetTradingDetails,
    LiveAccountSnapshot,
    OrderRequest,
    OrderSide,
    Position,
    RiskCheckResult,
    RiskDecision,
    ShortSellingPolicy,
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


def check_projected_order_risk(
    request: OrderRequest,
    *,
    account: LiveAccountSnapshot,
    market_price: float,
    short_policy: ShortSellingPolicy,
) -> RiskCheckResult:
    """Evaluate an order against the broker account state after a full fill.

    Signed projected positions let this check distinguish closing a long,
    opening a short, covering a short, and opening a long. Exposure checks use
    current position marks and the requested symbol's latest market price.
    """
    if market_price <= 0:
        return _rejected("market price must be positive")
    if account.equity <= 0:
        return _rejected("account equity must be positive")

    positions = {position.symbol: position for position in account.positions}
    current = positions.get(request.symbol)
    current_quantity = 0 if current is None else current.quantity
    signed_order_quantity = (
        request.quantity
        if request.side == OrderSide.BUY
        else -request.quantity
    )
    projected_quantity = current_quantity + signed_order_quantity
    opening_short_quantity = max(-projected_quantity, 0) - max(
        -current_quantity,
        0,
    )

    if opening_short_quantity > 0 and not short_policy.enabled:
        return _rejected("short selling is not enabled")

    current_values = {
        symbol: position.quantity * position.last_price
        for symbol, position in positions.items()
    }
    projected_values = {
        symbol: position.quantity * position.last_price
        for symbol, position in positions.items()
    }
    projected_values[request.symbol] = projected_quantity * market_price
    projected_values = {
        symbol: value
        for symbol, value in projected_values.items()
        if value != 0
    }

    projected_short_notional = abs(
        min(projected_values.get(request.symbol, 0), 0)
    )
    current_short_notional = abs(
        min(current_quantity * market_price, 0)
    )
    if (
        short_policy.max_short_position_notional is not None
        and projected_short_notional
        > short_policy.max_short_position_notional
        and projected_short_notional > current_short_notional
    ):
        return _rejected("projected short position exceeds symbol limit")

    current_total_short_exposure = sum(
        abs(value) for value in current_values.values() if value < 0
    )
    total_short_exposure = sum(
        abs(value) for value in projected_values.values() if value < 0
    )
    if (
        short_policy.max_total_short_exposure_pct_equity is not None
        and total_short_exposure / account.equity
        > short_policy.max_total_short_exposure_pct_equity
        and total_short_exposure > current_total_short_exposure
    ):
        return _rejected("projected total short exposure exceeds limit")

    current_gross_exposure = sum(
        abs(value) for value in current_values.values()
    )
    gross_exposure = sum(abs(value) for value in projected_values.values())
    if (
        short_policy.max_gross_exposure_pct_equity is not None
        and gross_exposure / account.equity
        > short_policy.max_gross_exposure_pct_equity
        and gross_exposure > current_gross_exposure
    ):
        return _rejected("projected gross exposure exceeds limit")

    opening_long_quantity = max(projected_quantity, 0) - max(
        current_quantity,
        0,
    )
    buying_power_charge = max(opening_long_quantity, 0) * market_price
    # Alpaca values market short orders at 3% above the current ask when
    # checking buying power. Use the same conservative cushion locally.
    buying_power_charge += (
        max(opening_short_quantity, 0) * market_price * 1.03
    )
    projected_buying_power = account.buying_power - buying_power_charge
    if projected_buying_power < 0:
        return _rejected("insufficient buying power")
    if (
        short_policy.min_buying_power_buffer_pct is not None
        and buying_power_charge > 0
        and projected_buying_power / account.equity
        < short_policy.min_buying_power_buffer_pct
    ):
        return _rejected("projected buying power buffer is too small")

    return RiskCheckResult(decision=RiskDecision.APPROVED)


def check_short_sale_availability(
    request: OrderRequest,
    *,
    account: LiveAccountSnapshot,
    asset: AssetTradingDetails,
) -> RiskCheckResult:
    """Require current broker borrow permission only for new short exposure."""
    if not opens_or_increases_short(request, account=account):
        return RiskCheckResult(decision=RiskDecision.APPROVED)
    if not asset.tradable:
        return _rejected("asset is not tradable")
    if not asset.shortable:
        return _rejected("asset is not shortable")
    if not asset.easy_to_borrow:
        return _rejected("asset is not easy to borrow")
    return RiskCheckResult(decision=RiskDecision.APPROVED)


def opens_or_increases_short(
    request: OrderRequest,
    *,
    account: LiveAccountSnapshot,
) -> bool:
    """Return whether a full fill would create additional short exposure."""
    current = next(
        (
            position
            for position in account.positions
            if position.symbol == request.symbol
        ),
        None,
    )
    current_quantity = 0 if current is None else current.quantity
    signed_order_quantity = (
        request.quantity
        if request.side == OrderSide.BUY
        else -request.quantity
    )
    projected_quantity = current_quantity + signed_order_quantity
    return max(-projected_quantity, 0) > max(
        -current_quantity,
        0,
    )


def _rejected(reason: str) -> RiskCheckResult:
    return RiskCheckResult(decision=RiskDecision.REJECTED, reason=reason)
