# Quant System

A small, typed, solo-maintainable quant system.

The first milestone is intentionally narrow:

1. Load historical prices from CSV.
2. Generate entries and exits from a typed strategy.
3. Run a VectorBT-backed signal backtest.
4. Return typed performance results.
5. Keep production code explicit enough that dictionary key tracing does not become a daily tax.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

If you prefer `uv` later:

```bash
uv sync --extra dev
```

The repository includes `uv.lock` so dependency resolution is reproducible
when using `uv`.

## First Backtest

```bash
quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
```

The command writes durable artifacts by default:

```text
data/results/latest/summary.json
data/results/latest/trades.csv
```

## Data Ingestion

The ingestion layer separates raw provider data from normalized data:

```bash
quant data ingest --provider yfinance --symbol AAPL --start 2024-01-01 --end 2024-02-01
```

This writes:

```text
data/raw/provider=yfinance/modality=market_bars/symbol=AAPL/...
data/normalized/market_bars/AAPL.csv
data/validation/market_bars/AAPL.json
data/metadata/market_bars/AAPL.json
```

Validate normalized data before backtesting it:

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

Validation also runs by default during ingestion and before CSV backtests. Use
`--skip-validation` only when intentionally debugging bad data.

Compare two normalized market-bar datasets before trusting a merged or
provider-swapped research run:

```bash
quant data reconcile --left path/to/provider_a.csv --right path/to/provider_b.csv --symbol AAPL
```

This writes a report under:

```text
data/reconciliation/AAPL.json
```

## Feature Engineering

Build technical features from normalized market bars:

```bash
quant features build --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

This writes:

```text
data/features/technical/AAPL.csv
```

Run a backtest that consumes a persisted feature artifact:

```bash
quant backtest --strategy feature-momentum --features-data data/features/technical/AAPL.csv --symbol AAPL
```

Use `--fast-feature` and `--slow-feature` to point the strategy at different
moving-average columns.

## Local Checks

```bash
make check
```

Or run the pieces separately:

```bash
make lint
make typecheck
make test
make backtest
```

## Design Rule

Dictionaries are allowed at system edges. Core domain logic uses typed models:

- market bars
- signals
- strategy configuration
- backtest metrics
- orders and fills, when added later

See [docs/code_style.md](docs/code_style.md).
