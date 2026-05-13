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
