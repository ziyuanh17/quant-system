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
```

Validate normalized data before backtesting it:

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

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
