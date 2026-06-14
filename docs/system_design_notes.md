# System Design Notes

This document explains the current implementation for a beginner who wants to
understand not only what exists, but why each part exists.

Most detailed examples below explain the original signal-oriented path. The
repository also contains the semantic-target architecture summarized in
[current_system_status.md](current_system_status.md) and specified in
[semantic_target_architecture.md](semantic_target_architecture.md).

The system is being built in layers:

```text
data
  -> validation and lineage
  -> features
  -> strategies
  -> backtests
  -> paper execution
  -> scheduling
  -> dashboard
```

Each layer owns one responsibility. That is the main design idea. When the
system grows, the goal is to avoid a large script where data fetching,
indicator math, strategy rules, order logic, and reporting are all mixed
together.

## Mental Model

The current repo is not yet a live trading system. It is a typed research and
paper-trading foundation.

Use this progression:

```text
Backtesting tests the idea.
Paper trading tests the machine.
Small real trading tests the machine against reality.
```

Backtesting answers whether a strategy looked good historically. Paper trading
answers whether the system can run correctly now without real money. Real
trading begins only when orders are sent to a real broker or exchange.

## Repository Shape

Important folders:

```text
src/quant/models/
src/quant/data/
src/quant/features/
src/quant/strategies/
src/quant/backtest/
src/quant/execution/
src/quant/scheduler/
docs/
site/
tests/
```

The most important convention is that core concepts are represented by typed
models instead of unstructured dictionaries. This helps prevent the common
Python pain point where a dictionary appears in the code and you must search
many files to discover which keys it contains.

For example:

- market data is represented by `PriceData` and `MarketBar`
- strategy signals are represented by `SignalFrame`
- backtest output is represented by `BacktestResult`
- paper orders and fills are represented by `Order`, `Fill`, and
  `PaperTradeRecord`
- scheduler attempts are represented by `ScheduledRunRecord`

## Data Layer

Relevant files:

```text
src/quant/data/
src/quant/models/market.py
src/quant/models/ingestion.py
```

The data layer separates raw provider data from normalized system data.

Current flow:

```text
provider response
  -> raw artifact
  -> normalized market-bar CSV
  -> validation report
  -> metadata record
```

This matters because downloaded data is not automatically strategy-ready. A
provider can change formats, revise values, omit rows, or use different
corporate-action rules. The system keeps raw data as evidence and normalized
data as the version used by the rest of the application.

Current implementation:

- `YFinanceMarketBarProvider` fetches market bars from yfinance.
- `normalize_market_bars` converts provider records into the local market-bar
  shape.
- `CsvMarketBarStore` writes normalized CSV files.
- `DatasetMetadata` records where the data came from and how it was processed.

## Validation And Reconciliation

Relevant files:

```text
src/quant/data/validation.py
src/quant/data/reconciliation.py
src/quant/models/validation.py
src/quant/models/reconciliation.py
```

Validation checks whether one dataset is internally usable. Reconciliation
compares two datasets from different sources.

Validation currently checks:

- required columns exist
- symbol values match expectation
- dates are valid and sorted
- duplicate dates are rejected
- prices are positive
- OHLC relationships make sense
- volume is non-negative

Reconciliation currently checks:

- both datasets contain required columns
- both contain the requested symbol
- duplicate dates
- dates present in only one source
- close-price differences
- volume differences

Close-price mismatches are treated as errors because they can change returns,
features, and trading decisions. Coverage and volume differences begin as
warnings because they may be explainable by calendars or provider methodology.

## Feature Layer

Relevant files:

```text
src/quant/features/
src/quant/models/features.py
```

A feature is a computed input to a strategy. For example:

```text
daily_return
log_return
ma_5
ma_20
volatility_20
momentum_20
drawdown
```

A feature artifact is the saved output of feature engineering, such as:

```text
data/features/technical/AAPL.csv
```

Saving features matters because it makes backtests easier to reproduce. A
strategy can point to the exact feature file it consumed instead of silently
recomputing indicators each time.

## Strategy Layer

Relevant files:

```text
src/quant/strategies/
src/quant/models/signals.py
```

Strategies convert data into entry and exit signals.

There are two strategy boundaries:

```text
Strategy
  -> consumes PriceData

FeatureStrategy
  -> consumes FeatureData
```

The current price-based strategy is `MomentumStrategy`. It uses moving-average
crossovers:

```text
fast moving average crosses above slow moving average -> entry
fast moving average crosses below slow moving average -> exit
```

The current feature-based strategy is `FeatureMomentumStrategy`. It consumes
precomputed feature columns instead of calculating moving averages internally.

Signals are stored in `SignalFrame`:

```text
entries: boolean series
exits: boolean series
```

Keeping signals typed and aligned by date is important because later execution
logic needs to know exactly which row produced a trade decision.

## Backtesting Layer

Relevant files:

```text
src/quant/backtest/
src/quant/models/backtest.py
```

Backtesting uses historical data to simulate how a strategy would have behaved.

Current flow:

```text
PriceData or FeatureData
  -> strategy signals
  -> VectorBT portfolio simulation
  -> BacktestResult
  -> summary.json and trades.csv
```

VectorBT is used as the simulation engine. The application still owns the data
contracts, strategy interfaces, and artifact writing. That is deliberate:
VectorBT is powerful, but it should not become the entire architecture.

## Paper Execution Layer

Relevant files:

```text
src/quant/execution/
src/quant/models/execution.py
```

Paper trading is simulated trading. It does not send real orders and does not
move real money.

The current paper execution flow:

```text
OrderRequest
  -> risk check
  -> PaperBroker
  -> Fill or rejection
  -> PortfolioSnapshot
  -> PaperTradeRecord
```

Important models:

- `OrderRequest`: the intent to trade
- `RiskCheckResult`: whether the order is allowed
- `Order`: the paper broker's record of the request
- `Fill`: the simulated execution
- `Position`: simulated holdings
- `PortfolioSnapshot`: cash, positions, and equity
- `PaperTradeRecord`: audit record for an order attempt

The current `PaperBroker` is deterministic. Market orders fill at an explicit
price supplied by the caller. This keeps tests repeatable and makes audit
records easy to understand.

## Paper Signal Execution

Relevant file:

```text
src/quant/execution/signal_execution.py
```

Paper signal execution connects strategies to paper trading:

```text
PriceData
  -> Strategy
  -> latest SignalFrame row
  -> PaperSignalDecision
  -> PaperBroker
  -> PaperSignalRecord
```

The current version reads the latest strategy signal:

- latest entry signal means `buy`
- latest exit signal means `sell`
- no latest signal means `hold`

This is the first research-to-paper path. The paper order is no longer purely
manual; it comes from strategy output.

Current limitation: the first version uses one symbol, the price-based
momentum strategy, and local CSV data. Future versions should support
feature-based strategies, multi-symbol execution, idempotency, and automatic
data refresh before signal generation.

## Scheduler Layer

Relevant files:

```text
src/quant/scheduler/
src/quant/models/scheduler.py
```

The scheduler runs a task and writes a durable run record:

```text
scheduled task
  -> SchedulerRunner
  -> ScheduledRunRecord
  -> task artifacts
```

The current scheduler is a finite loop. It can run once or a fixed number of
iterations. It is not a permanent daemon yet.

That is intentional. Finite loops are safer while the system is young. They can
be called from cron, GitHub Actions, systemd timers, or another server process
later.

Future scheduler work should add:

- retries
- idempotency keys
- structured logs
- failure notifications
- heartbeat records
- service deployment documentation

## CLI Layer

Relevant file:

```text
src/quant/cli.py
```

The CLI is the operator interface. It lets you run pieces of the system without
writing Python scripts.

Important commands:

```bash
quant data ingest
quant data validate
quant data reconcile
quant features build
quant backtest
quant paper order
quant schedule paper-order
quant schedule paper-signal
```

These commands are intentionally explicit. Explicit commands are easier to
debug than a hidden pipeline that does many things at once.

## Dashboard

Relevant files:

```text
site/index.html
site/progress.json
site/app.js
site/styles.css
.github/workflows/pages.yml
```

The dashboard is a static GitHub Pages site. Today it tracks project progress.
Later, it can read generated JSON artifacts to display operational metrics.

Possible future metrics:

- latest paper equity
- latest paper cash
- open paper positions
- last strategy signal
- last scheduler run status
- latest backtest return
- latest validation status

GitHub Pages is static, so it is not true real-time streaming. But a scheduled
job can periodically write JSON files, and the dashboard can display the latest
available values.

## Why The v1 Labels Exist

Many milestones are labeled `v1` because they establish a boundary, not because
the topic is complete.

Examples:

- validation exists, but does not yet know exchange calendars
- storage has a CSV implementation, but not Parquet
- reconciliation compares two CSV files, but not many providers
- paper trading exists, but only with deterministic fills
- scheduler exists, but not as a supervised service

The roadmap records these follow-ups so they do not get lost.

## Current Weak Spots To Remember

The most important known limitations are:

- paper broker state needs persistence
- paper signal execution needs duplicate-signal prevention
- strategy configuration should be persisted with run records
- features and backtests should reference upstream artifact IDs
- CI should eventually use the lockfile for dependency consistency
- the dashboard should eventually read generated operational JSON
- scheduled jobs need retries, idempotency, and alerting

These are normal for this stage. The important thing is that the boundaries are
now visible and typed, so each future improvement has a natural place to live.
