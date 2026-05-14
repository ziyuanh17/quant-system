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
| 10 | Strategy feature interface | In Review | Let strategies consume typed feature inputs instead of raw price frames only. |
| 11 | Provider reconciliation | Planned | Add checks and policies for comparing or combining data from multiple providers. |
| 12 | Paper trading foundation | Planned | Add paper broker, risk checks, order records, portfolio snapshots, and scheduler loop. |

## Current Recommendation

The next milestone after the in-review strategy feature interface work should be
**Provider Reconciliation**.

Feature strategies make the research loop more reproducible because the
backtest can point to the exact feature artifact it consumed. After that,
provider reconciliation becomes the next data-quality priority: the system
should make contradictions across sources visible before they leak into
features, simulations, or trading decisions.

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
