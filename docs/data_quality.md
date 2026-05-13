# Data Quality Guidance

Data quality is a first-class part of this quant system. It is not plumbing.

A strategy can only be as trustworthy as the data path below it:

```text
raw data
  -> normalized data
  -> validated data
  -> features
  -> signals
  -> backtest or execution
```

Bad data often does not crash a backtest. It usually creates clean-looking
charts, plausible metrics, and false confidence.

## Core Principle

Never treat downloaded data as strategy-ready data.

Every dataset should move through explicit stages:

```text
provider response
  -> immutable raw artifact
  -> normalized domain dataset
  -> validation report
  -> downstream consumption
```

Raw data is evidence. Normalized data is interpretation.

## Common Data Risks

### Look-Ahead Bias

Look-ahead bias happens when a backtest uses information that would not have
been available at the simulated decision time.

This can happen with:

- restated fundamentals
- revised macroeconomic data
- future index membership
- corporate actions applied with future knowledge
- news timestamps based on ingestion time instead of publication time
- features calculated using future rows by accident

The dangerous part is that the data may be factually correct today while still
being invalid for a historical simulation.

### Survivorship Bias

Survivorship bias happens when historical tests only include assets that still
exist today.

For example, testing a stock strategy on current S&P 500 constituents and
pretending that was the historical universe will usually overstate performance.
The failed, delisted, acquired, or removed companies are missing.

### Corporate Action Errors

Equity data must handle splits, dividends, mergers, ticker changes, and
delistings carefully.

Adjusted and unadjusted prices answer different questions. Mixing them without
an explicit policy can corrupt returns, positions, and signals.

### Provider Contradictions

Different providers may disagree because they use different:

- exchange feeds
- corporate action policies
- timestamps and time zones
- session calendars
- symbol mappings
- delayed correction policies
- adjusted-price calculations
- survivorship rules

Using multiple providers is useful for reconciliation, but dangerous if the
system silently merges them without explicit rules.

### Timestamp Ambiguity

Every time-sensitive record should distinguish:

- when the event happened
- when the provider says it happened
- when we ingested it
- when it became available to a strategy

This matters for market bars, news, filings, economic releases, and alternative
data.

## Project Rules

### Keep Raw Data Immutable

Do not overwrite raw provider responses.

If a provider later corrects data, store the new response as a new raw artifact.
The system can decide which version to normalize, but it should not destroy the
original evidence.

### Separate Raw, Normalized, Validated, And Feature Data

Use separate layers:

```text
data/raw/
data/normalized/
data/features/
data/results/
```

Do not make strategy code fetch or reshape provider data directly.

### Store Dataset Metadata

Every normalized dataset should eventually be traceable to:

- provider
- modality
- symbol or universe
- requested start/end
- ingestion timestamp
- source timestamp policy
- normalization version
- validation report
- adjustment policy

Backtest results should eventually reference the exact data artifacts they used.

### Prefer One Source Per Domain At First

Start with one provider for each data domain:

```text
market bars -> one provider
news -> one provider
fundamentals -> one provider
filings -> one provider
```

Add additional providers for comparison and reconciliation only after the
primary path is reliable.

### Validate Before Consumption

Normalized data should be validated before it reaches backtests or live logic.

For market bars, minimum validation includes:

- required columns exist
- symbol values match expectation
- no duplicate dates
- dates are sorted
- no missing OHLCV values
- prices are positive
- `high >= low`
- `high >= open`
- `high >= close`
- `low <= open`
- `low <= close`
- volume is non-negative
- enough rows exist for the intended use

This project implements these checks through:

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

Validation also runs by default during ingestion and before CSV backtests.

## Multi-Modal Data

The same principles apply beyond market prices.

### News

News ingestion should preserve:

- raw article/API response
- provider article ID
- source/publisher
- publication timestamp
- ingestion timestamp
- URL
- extracted symbols/entities
- text normalization version

Strategies should not consume raw articles directly. They should consume typed
features such as:

```text
sentiment_score_1d
news_volume_1d
earnings_event_today
regulatory_event_flag
```

### Filings

Filings should preserve:

- raw filing document
- filing timestamp
- accepted timestamp
- accession number
- company identifiers
- extracted sections
- parser version

Point-in-time availability is essential.

### Social Or Alternative Data

Alternative data should track:

- source identity
- collection timestamp
- event timestamp
- deduplication policy
- bot/spam filtering policy
- entity mapping method
- feature extraction version

Alternative data is especially easy to overfit, so validation and provenance
matter even more.

## Red Flags

Pause before trusting a backtest if:

- data comes from multiple providers without reconciliation rules
- the dataset has no raw artifact
- the dataset has no validation report
- symbol mappings are implicit
- adjusted-price policy is unknown
- fundamentals or news are not point-in-time
- index membership is based on today’s constituents
- the strategy reads provider data directly
- a backtest result cannot identify the exact data artifacts it used

## Near-Term Roadmap

The data layer should evolve toward:

```text
ingest
  -> normalize
  -> validate
  -> write validation report
  -> register dataset metadata
  -> compute features
  -> backtest
```

The next important improvements are:

- write validation reports as artifacts
- add dataset metadata files
- record data artifact paths in backtest results
- add explicit adjusted/unadjusted price policy
- add provider reconciliation checks before mixing sources

## References

- QuantStart, “Successful Backtesting of Algorithmic Trading Strategies”
- SEC market structure materials on consolidated data and market-data limits
- General backtesting literature on look-ahead bias, survivorship bias, and
  point-in-time data
