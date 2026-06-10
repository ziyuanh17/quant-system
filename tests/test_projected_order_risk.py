from quant.execution import (
    check_projected_order_risk,
    check_short_sale_availability,
)
from quant.models.execution import (
    AssetTradingDetails,
    LiveAccountSnapshot,
    OrderRequest,
    OrderSide,
    Position,
    ShortSellingPolicy,
)


def test_projected_risk_rejects_short_when_policy_is_disabled() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=1),
        account=_account(),
        market_price=100,
        short_policy=ShortSellingPolicy(),
    )

    assert not result.approved
    assert result.reason == "short selling is not enabled"


def test_short_availability_rejects_new_unborrowable_short() -> None:
    result = check_short_sale_availability(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=1),
        account=_account(),
        asset=AssetTradingDetails(
            symbol="AAPL",
            tradable=True,
            shortable=True,
            easy_to_borrow=False,
        ),
    )

    assert not result.approved
    assert result.reason == "asset is not easy to borrow"


def test_short_availability_does_not_block_cover() -> None:
    result = check_short_sale_availability(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
        account=_account(
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=-2,
                    average_price=100,
                    last_price=100,
                ),
            )
        ),
        asset=AssetTradingDetails(
            symbol="AAPL",
            tradable=False,
            shortable=False,
            easy_to_borrow=False,
        ),
    )

    assert result.approved


def test_projected_risk_allows_cover_when_short_policy_is_disabled() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
        account=_account(
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=-2,
                    average_price=100,
                    last_price=100,
                ),
            )
        ),
        market_price=100,
        short_policy=ShortSellingPolicy(),
    )

    assert result.approved


def test_projected_risk_allows_reducing_an_over_limit_short() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.BUY, quantity=1),
        account=_account(
            positions=(
                Position(
                    symbol="AAPL",
                    quantity=-4,
                    average_price=100,
                    last_price=100,
                ),
            )
        ),
        market_price=100,
        short_policy=_enabled_policy(max_short_position_notional=200),
    )

    assert result.approved


def test_projected_risk_allows_bounded_short() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        account=_account(),
        market_price=100,
        short_policy=_enabled_policy(),
    )

    assert result.approved


def test_projected_risk_rejects_oversized_symbol_short() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=3),
        account=_account(),
        market_price=100,
        short_policy=_enabled_policy(max_short_position_notional=250),
    )

    assert not result.approved
    assert result.reason == "projected short position exceeds symbol limit"


def test_projected_risk_rejects_total_short_exposure_limit() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        account=_account(
            positions=(
                Position(
                    symbol="MSFT",
                    quantity=-2,
                    average_price=100,
                    last_price=100,
                ),
            )
        ),
        market_price=100,
        short_policy=_enabled_policy(max_total_short_exposure_pct_equity=0.3),
    )

    assert not result.approved
    assert result.reason == "projected total short exposure exceeds limit"


def test_projected_risk_rejects_gross_exposure_limit() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        account=_account(
            positions=(
                Position(
                    symbol="MSFT",
                    quantity=8,
                    average_price=100,
                    last_price=100,
                ),
            )
        ),
        market_price=100,
        short_policy=_enabled_policy(max_gross_exposure_pct_equity=0.5),
    )

    assert not result.approved
    assert result.reason == "projected gross exposure exceeds limit"


def test_projected_risk_rejects_buying_power_buffer_breach() -> None:
    result = check_projected_order_risk(
        OrderRequest(symbol="AAPL", side=OrderSide.SELL, quantity=2),
        account=_account(buying_power=250),
        market_price=100,
        short_policy=_enabled_policy(min_buying_power_buffer_pct=0.1),
    )

    assert not result.approved
    assert result.reason == "projected buying power buffer is too small"


def _account(
    *,
    buying_power: float = 1000,
    positions: tuple[Position, ...] = (),
) -> LiveAccountSnapshot:
    return LiveAccountSnapshot(
        broker_name="alpaca-paper",
        account_id="acct-1",
        broker_environment="paper",
        cash=1000,
        buying_power=buying_power,
        positions=positions,
    )


def _enabled_policy(
    *,
    max_short_position_notional: float = 500,
    max_total_short_exposure_pct_equity: float = 0.5,
    max_gross_exposure_pct_equity: float = 1.5,
    min_buying_power_buffer_pct: float = 0.1,
) -> ShortSellingPolicy:
    return ShortSellingPolicy(
        enabled=True,
        max_short_position_notional=max_short_position_notional,
        max_total_short_exposure_pct_equity=max_total_short_exposure_pct_equity,
        max_gross_exposure_pct_equity=max_gross_exposure_pct_equity,
        min_buying_power_buffer_pct=min_buying_power_buffer_pct,
    )
