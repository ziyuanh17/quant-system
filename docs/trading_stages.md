# Trading Stages

This project separates three ideas that are easy to mix up:

```text
backtesting
  -> paper trading
  -> real trading
```

They are related, but they answer different questions.

## Backtesting

Backtesting asks:

```text
Would this strategy have worked in the past?
```

It runs over historical data, usually very quickly:

```text
historical prices
  -> historical signals
  -> simulated trades
  -> performance metrics
```

Backtesting is mostly about strategy research. It helps evaluate historical
return, drawdown, trade count, and other metrics before spending time on
real-time execution.

Backtesting does not prove future profit. It can also look better than reality
if data quality, look-ahead bias, survivorship bias, fees, slippage, or
execution assumptions are wrong.

## Paper Trading

Paper trading asks:

```text
Can the system trade correctly now without using real money?
```

It is a live rehearsal. The system behaves as if it is trading, but it does not
send orders to a real broker or exchange:

```text
current data
  -> current signal
  -> risk check
  -> simulated order
  -> simulated fill
  -> simulated position update
  -> portfolio snapshot
  -> audit record
```

Paper trading is not trying to preserve a specific market opportunity. If the
paper system says it would have bought at 10:01:03, that exact moment is already
gone. The point is to test the machine while time is moving.

Paper trading helps catch operational mistakes such as:

- data did not refresh
- timestamps are wrong
- the strategy generated duplicate orders
- the system tried to sell shares it does not own
- position sizing is wrong
- risk checks are missing
- portfolio state is not updated correctly
- audit records are not written
- the server job fails or runs twice

These failures can be expensive with real money, even when the strategy idea is
reasonable.

## Real Trading

Real trading starts only when the system sends orders to an actual broker or
exchange with real money.

Real trading adds risks that paper trading cannot fully simulate:

- slippage
- partial fills
- rejected broker orders
- fees and borrow costs
- broker outages
- exchange halts
- latency
- market impact
- emotional pressure

This is why the usual progression is:

```text
backtest
  -> paper trade
  -> tiny real-money trade
  -> gradually larger real-money trade
```

Paper trading is not a guarantee that real trading will work. It is a safety
step before real money is involved.

## Components In This Repo

The current paper-trading foundation uses:

- `OrderRequest`: the intent to trade, such as buy 10 shares of AAPL
- `RiskCheckResult`: whether the order is allowed
- `Order`: the broker-side record of the request
- `Fill`: the simulated execution price and quantity
- `Position`: current simulated holdings
- `PortfolioSnapshot`: cash, positions, and total equity after the order
- `PaperTradeRecord`: the audit record tying order, fill, and portfolio state

The first paper broker is deliberately deterministic. Market orders fill at a
supplied price, which makes tests and audit records easy to inspect. Later
milestones can connect this execution boundary to scheduled strategy runs,
market data refreshes, and eventually a real broker adapter.

## Mental Model

Use this rule of thumb:

```text
Backtesting tests the idea.
Paper trading tests the machine.
Small real trading tests the machine against reality.
```
