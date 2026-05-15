# Architecture

This repo starts as a research/backtest core and is shaped so it can later grow into
paper trading and live trading without replacing the strategy layer.

## Current Flow

```text
CSV prices
  -> data loader
  -> strategy signal generation
  -> VectorBT backtest adapter
  -> typed BacktestResult
```

## Data Layer

Raw ingestion is modality-agnostic. Normalization is modality-specific.

```text
provider
  -> RawDataset
  -> raw file under data/raw/
  -> normalized modality dataset under data/normalized/
  -> features/signals
  -> backtest or execution
```

Supported modality contracts are intentionally broader than market bars:

- `market_bars`
- `news_article`
- `filing`
- `social_post`

The first concrete provider is `yfinance` for market bars. Future providers
for news, filings, social data, or embeddings should implement the same
provider boundary and add modality-specific normalizers.

Normalized market bars are written through a store boundary:

```text
MarketBarStore
  -> CsvMarketBarStore
  -> future ParquetMarketBarStore
```

This keeps ingestion from depending directly on CSV path construction.

Provider reconciliation compares normalized market-bar datasets before they
feed features or backtests:

```text
normalized provider A
  -> ProviderReconciliationReport
normalized provider B
```

The first reconciliation checks coverage, close-price differences, volume
differences, duplicate dates, missing symbols, and missing required columns.

## Feature Layer

Feature engineering consumes normalized and validated market bars, then writes
feature artifacts under:

```text
data/features/
```

Feature artifacts should eventually carry lineage back to the normalized
dataset and validation report that produced them.

## Strategy Layer

Strategies have two input contracts:

```text
Strategy
  -> consumes PriceData

FeatureStrategy
  -> consumes FeatureData
```

Keeping these protocols separate makes a backtest's inputs easier to audit.
Price-based strategies can still recompute indicators during early research,
while feature-based strategies consume persisted feature columns by name.

## Execution Layer

Paper trading starts with a deterministic broker boundary:

```text
OrderRequest
  -> risk check
  -> PaperBroker
  -> Fill or rejection
  -> PortfolioSnapshot
  -> PaperTradeRecord
```

The first implementation simulates market orders at an explicit supplied price.
That keeps tests deterministic and makes the audit trail easy to inspect before
the system grows into scheduled signal execution or external broker APIs.

See [trading_stages.md](trading_stages.md) for the beginner-level distinction
between backtesting, paper trading, and real trading.

## Scheduler Layer

Scheduled runs produce durable run records:

```text
scheduled task
  -> SchedulerRunner
  -> ScheduledRunRecord
  -> task artifacts
```

The first scheduler is a finite loop, not a forever-running daemon. That keeps
local tests and server jobs predictable while still giving the system a
repeatable boundary for future cron, service, or worker deployment.

Paper signal execution connects the strategy and execution layers:

```text
PriceData
  -> Strategy
  -> latest SignalFrame row
  -> PaperSignalDecision
  -> PaperBroker
  -> PaperSignalRecord
```

This is the first research-to-paper path. It still uses local CSV data and a
deterministic paper broker, but the order side now comes from a strategy signal
instead of a manually specified CLI option.

Paper broker state is persisted separately from per-run audit records:

```text
PaperBrokerState
  -> PaperBroker
  -> temporary state file
  -> atomic replace
  -> updated PaperBrokerState
```

That lets separate scheduled processes behave like one continuous paper account
instead of restarting cash and positions on every invocation.

State writes keep one `.bak` copy of the previous state. The live JSON file is
replaced only after the new state has been written and flushed, so an
interrupted write should not leave a partial paper account file behind.

The paper state also stores processed signal keys:

```text
strategy:symbol:signal_date:action
```

This prevents duplicate paper orders when a scheduler sees the same actionable
signal more than once. Duplicate signals still write audit records, but they
are marked as skipped and do not change cash or positions.

Paper state reconciliation replays signal audit records back into expected
account state:

```text
PaperSignalRecord
  -> filled trade replay
  -> expected PaperBrokerState
  -> PaperStateReconciliationReport
```

This is read-only. It detects drift between the persisted state file and the
paper decisions and fills that produced it.

## Workflow Layer

Workflows compose existing boundaries into ordered operational paths:

```text
RunLockRecord
  -> provider refresh
  -> validation and lineage
  -> scheduled paper signal
  -> DataRefreshWorkflowRecord
```

The first workflow refreshes one provider-backed market-bar dataset before
paper signal execution. If validation fails, paper execution does not run. The
workflow record links the refreshed data artifacts to the scheduler records and
paper artifacts that followed. A lock file prevents overlapping workflow runs
from refreshing data or mutating the same paper state at the same time.

Deployment starts as a wrapper script plus environment file:

```text
.env
  -> scripts/run_paper_signal_refresh.sh
  -> quant workflow paper-signal-refresh
  -> logs and artifacts
```

This keeps the runtime contract explicit before introducing cloud services,
alerts, or process supervision.

## Operations Layer

Operational health is derived from durable local artifacts:

```text
ScheduledRunRecord
  -> PaperSignalRecord
  -> PaperBrokerState
  -> wrapper logs
  -> HealthReport
```

The first health command is read-only. It does not place orders, refresh data,
or mutate paper state. That separation matters because operational checks
should be safe to run from a shell, cron, CI, or a future alerting hook.

## Intended Growth

```text
data providers
  -> raw storage
  -> normalized storage
  -> feature pipeline
  -> strategy engine
  -> risk engine
  -> paper/live execution
  -> broker reconciliation
  -> monitoring and reports
```

## Boundary Principle

VectorBT is a research and analytics engine. It should not own the whole application.

The application owns:

- data contracts
- strategy interfaces
- risk models
- broker/execution models
- scheduling
- audit logs

VectorBT owns:

- fast vectorized backtests
- signal portfolio simulation
- metrics and research visualization
