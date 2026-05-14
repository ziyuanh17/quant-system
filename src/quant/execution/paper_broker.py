from quant.execution.risk import check_order_risk
from quant.models.execution import (
    Fill,
    Order,
    OrderRequest,
    OrderSide,
    OrderStatus,
    PaperTradeRecord,
    PortfolioSnapshot,
    Position,
)


class PaperBroker:
    """Deterministic broker for rehearsing execution without real orders."""

    def __init__(self, *, initial_cash: float) -> None:
        if initial_cash <= 0:
            raise ValueError("initial_cash must be positive")
        self._cash = initial_cash
        self._positions: dict[str, Position] = {}

    @property
    def cash(self) -> float:
        return self._cash

    @property
    def positions(self) -> dict[str, Position]:
        return dict(self._positions)

    def snapshot(self) -> PortfolioSnapshot:
        return PortfolioSnapshot(
            cash=self._cash,
            positions=tuple(
                sorted(self._positions.values(), key=lambda item: item.symbol)
            ),
        )

    def submit_market_order(
        self, request: OrderRequest, *, market_price: float
    ) -> PaperTradeRecord:
        risk = check_order_risk(
            request,
            cash=self._cash,
            positions=self._positions,
            market_price=market_price,
        )
        if not risk.approved:
            order = Order(
                request=request,
                status=OrderStatus.REJECTED,
                risk=risk,
            )
            return PaperTradeRecord(
                order=order, fill=None, snapshot=self.snapshot()
            )

        order = Order(
            request=request,
            status=OrderStatus.FILLED,
            risk=risk,
        )
        fill = Fill(
            order_id=order.id,
            symbol=request.symbol,
            side=request.side,
            quantity=request.quantity,
            price=market_price,
        )
        self._apply_fill(fill)
        return PaperTradeRecord(
            order=order, fill=fill, snapshot=self.snapshot()
        )

    def _apply_fill(self, fill: Fill) -> None:
        if fill.side == OrderSide.BUY:
            self._cash -= fill.notional
            self._positions[fill.symbol] = _apply_buy(
                self._positions.get(fill.symbol), fill
            )
        else:
            self._cash += fill.notional
            updated = _apply_sell(self._positions[fill.symbol], fill)
            if updated.quantity == 0:
                del self._positions[fill.symbol]
            else:
                self._positions[fill.symbol] = updated


def _apply_buy(position: Position | None, fill: Fill) -> Position:
    if position is None:
        return Position(
            symbol=fill.symbol,
            quantity=fill.quantity,
            average_price=fill.price,
            last_price=fill.price,
        )

    total_quantity = position.quantity + fill.quantity
    # Weighted average preserves the cost basis needed for future P&L reports.
    average_price = (
        position.average_price * position.quantity + fill.notional
    ) / total_quantity
    return Position(
        symbol=position.symbol,
        quantity=total_quantity,
        average_price=average_price,
        last_price=fill.price,
    )


def _apply_sell(position: Position, fill: Fill) -> Position:
    remaining_quantity = position.quantity - fill.quantity
    return Position(
        symbol=position.symbol,
        quantity=remaining_quantity,
        average_price=position.average_price,
        last_price=fill.price,
    )
