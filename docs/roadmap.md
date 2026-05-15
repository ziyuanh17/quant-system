# Roadmap

This document tracks the intended build order for the quant system.

It exists so we do not lose the thread as design questions branch into useful
side discussions.

## Status Legend

- `Done`: implemented and checked in
- `In Review`: implemented locally but not yet committed
- `Next`: recommended next implementation milestone
- `Planned`: not started

## Milestones

| Order | Milestone | Status | Purpose |
| --- | --- | --- | --- |
| 1 | Repo scaffold | Done | Establish Python project layout, typed domain models, CLI, tests, docs, and VectorBT-backed backtest path. |
| 2 | GitHub and CI foundation | Done | Add GitHub repo, CI, Makefile commands, `uv.lock`, and repeatable local checks. |
| 3 | Backtest artifacts | Done | Save durable backtest summaries and trade outputs under `data/results/`. |
| 4 | Multi-modal ingestion foundation | Done | Add provider interface, modality-aware raw dataset models, yfinance market-bar ingestion, normalized market-bar output, and news/text data model placeholders. |
| 5 | Data validation v1 | Done | Add market-bar validation checks and `quant data validate`. |
| 6 | Validation guardrails | Done | Run validation by default during ingestion and before CSV backtests; allow explicit `--skip-validation`. |
| 7 | Data lineage v1 | Done | Persist validation reports and dataset metadata that link raw data, normalized data, provider, symbol, timestamps, and normalization version. |
| 8 | Storage abstraction v1 | Done | Add a `MarketBarStore` boundary so CSV can later be swapped or complemented with Parquet. |
| 9 | Feature engineering v1 | Done | Compute and persist feature datasets from normalized/validated data. |
| 10 | Strategy feature interface | Done | Let strategies consume typed feature inputs instead of raw price frames only. |
| 11 | Provider reconciliation | Done | Add checks and policies for comparing or combining data from multiple providers. |
| 12 | Paper trading foundation | Done | Add paper broker, risk checks, order records, portfolio snapshots, and audit records. |
| 13 | Scheduler Loop v1 | Done | Add finite scheduled task runs with durable run records. |
| 14 | Paper Signal Execution v1 | Done | Connect strategy signals to scheduled paper-trading decisions. |
| 15 | Broker State Persistence v1 | Done | Persist paper account cash and positions across scheduled runs. |
| 16 | Idempotent Paper Signals v1 | In Review | Prevent duplicate paper orders for repeated signal processing. |

## Current Recommendation

The next milestone after the in-review idempotent paper signals work should be
**Service Deployment v1**.

Idempotent paper signals make repeated scheduled runs safer. The next step
should document and scaffold how this system runs as an actual server job with
logs, environment variables, and operational checks.

## Corrected Near-Term Order

```text
data ingestion
  -> data validation
  -> validation guardrails
  -> data lineage
  -> storage abstraction
  -> feature engineering
  -> strategy feature interface
  -> provider reconciliation
  -> paper trading foundation
  -> scheduler loop
  -> paper signal execution
  -> broker state persistence
  -> idempotent paper signals
  -> service deployment
```

## Data Lineage v1 Scope

When implemented, each ingest run should produce:

```text
raw provider artifact
normalized dataset
validation report artifact
dataset metadata artifact
```

The metadata should link:

- provider
- modality
- symbol
- request start/end
- raw path
- normalized path
- validation report path
- ingestion timestamp
- normalization version
- validation status

## Storage Abstraction v1 Scope

Introduce:

```text
MarketBarStore
CsvMarketBarStore
```

Keep CSV as the first implementation. Add Parquet later without changing
strategy or ingestion logic deeply.

## Feature Engineering v1 Scope

Start with simple technical features:

- daily returns
- rolling volatility
- moving averages
- momentum
- drawdown

Feature outputs should be artifacts with lineage back to the normalized dataset
and validation report that produced them.

## Strategy Feature Interface Scope

Introduce:

```text
FeatureData
FeatureStrategy
FeatureMomentumStrategy
```

Keep price-based strategies working. Feature-based strategies should consume a
named feature artifact and explicitly declare which feature columns drive their
signals, so later debugging can trace a backtest from result to signal columns
to feature file to normalized input data.

## Provider Reconciliation Scope

Introduce:

```text
ProviderReconciliationReport
ReconciliationDifference
quant data reconcile
```

The first version compares two normalized market-bar CSVs for one symbol. It
checks date coverage, required columns, duplicate dates, close-price
differences, and volume differences. Close mismatches are treated as errors;
coverage and volume mismatches start as warnings so they are visible without
blocking every exploratory run.

## Paper Trading Foundation Scope

Introduce:

```text
PaperBroker
OrderRequest
Order
Fill
Position
PortfolioSnapshot
RiskCheckResult
PaperTradeRecord
quant paper order
```

The first version supports deterministic market-order simulation at a supplied
price. It rejects impossible buys and sells, updates cash and positions, and
writes JSON audit records. It is not a live broker integration and does not yet
run strategies automatically on a schedule.

## Known v1 Follow-Ups

The `v1` label means the boundary exists and is useful, not that the area is
complete. Keep these follow-ups visible when planning future milestones.

| Area | Current v1 Limitation | Future Improvement |
| --- | --- | --- |
| Data validation | Checks one normalized market-bar CSV for one symbol at a time. | Add exchange calendars, expected session coverage, adjusted/unadjusted policy checks, split/dividend sanity checks, and configurable warning/error severity. |
| Data lineage | Ingestion writes metadata, but feature and backtest artifacts do not yet fully reference upstream artifact IDs. | Add stable dataset IDs and make feature artifacts, backtest summaries, paper trade records, and future live orders reference exact input artifacts. |
| Storage abstraction | `MarketBarStore` supports CSV only. | Add Parquet storage, partitioning by provider/symbol/date, schema version metadata, and migration checks. |
| Feature engineering | Only simple technical market-bar features are implemented. | Add feature metadata, lineage links, point-in-time guards, feature registry, multi-symbol features, and non-price modalities such as news sentiment. |
| Strategy feature interface | Feature strategies consume a CSV artifact and named columns, but there is no feature registry or feature schema contract yet. | Add declared feature requirements, compatibility checks, strategy parameter serialization, and richer signal audit records. |
| Provider reconciliation | Compares two normalized market-bar CSVs for one symbol. | Add multi-provider policies, canonical-source selection, adjusted-price comparison rules, calendar-aware coverage checks, reconciliation history, and severity configuration. |
| Paper trading | Simulates deterministic market orders but still omits slippage, fees, partial fills, and broker-specific behavior. | Model slippage/fees/partial fills, add order idempotency, and separate paper broker adapters from real broker adapters. |
| Paper signal execution | Uses the latest row of one price-based momentum strategy and local CSV data. | Support feature-based strategies, persisted strategy configs, multi-symbol runs, and data refresh steps before signal generation. |
| Broker state persistence | Persists one JSON paper account state file, with no locking or transaction semantics. | Add atomic writes, file locks, account IDs, state history, reconciliation against audit records, and backup/restore tools. |
| Idempotent paper signals | Uses simple strategy/symbol/date/action keys and local JSON state. | Add account-scoped idempotency, signal revision IDs, configurable reprocessing policy, and reconciliation between skipped records and trade records. |
| CLI workflow | Commands are useful but mostly single-step. | Add composed workflows for ingest, validate, reconcile, feature build, backtest, and paper execution with shared run IDs. |
| CI and dependency management | CI installs from broad dependency ranges even though `uv.lock` exists. | Make CI use the lockfile or otherwise pin critical tool versions to reduce dependency drift between local and GitHub runs. |
| Scheduler loop | Runs finite tasks and writes run records, but does not yet supervise a long-running process. | Add retries, idempotency keys, structured logs, failure notifications, and service/cron deployment docs. |
| Server operation | No service process, health checks, or alerting yet. | Add service supervision, heartbeat records, health checks, structured logs, and failure notifications. |

## Scheduler Loop v1 Scope

Introduce:

```text
SchedulerRunner
ScheduledTaskResult
ScheduledRunRecord
quant schedule paper-order
```

The first scheduler runs a task once or for a finite number of iterations. It
writes one JSON run record per attempt and points each run record at task
artifacts, such as paper trade records. It is intentionally not a permanent
daemon yet.

## Paper Signal Execution v1 Scope

Introduce:

```text
PaperSignalDecision
PaperSignalRecord
decide_latest_signal
execute_latest_signal
quant schedule paper-signal
```

The first version converts the latest momentum strategy signal into a paper
decision. Entry signals buy, exit signals sell, and no signal records a hold.
It writes paper signal records and scheduler run records so the research-to-paper
path is auditable.

## Broker State Persistence v1 Scope

Introduce:

```text
PaperBrokerState
load_paper_broker_state
save_paper_broker_state
--state-path
```

The first version stores paper account cash and positions as JSON. Scheduled
paper signal runs load this state before generating orders and save the updated
state after each run, so separate process invocations can behave like one
continuous paper account.

## Idempotent Paper Signals v1 Scope

Introduce:

```text
PaperSignalDecision.idempotency_key
PaperBrokerState.processed_signal_keys
PaperSignalRecord.skipped
```

The first version prevents duplicate paper orders for the same strategy, symbol,
signal date, and action. Duplicate signals still produce paper signal records,
but those records are marked as skipped and do not change cash or positions.
