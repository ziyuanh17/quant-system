# Runbook

## Local Backtest

```bash
quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
```

## Ingest Market Data

```bash
quant data ingest --provider yfinance --symbol AAPL --start 2024-01-01 --end 2024-02-01
```

The normalized file can then be used for a backtest:

```bash
quant backtest --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

## Validate Market Data

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

Validation failures return a nonzero exit code so scheduled jobs can stop
before bad data reaches a strategy.

Ingestion and backtesting run this validation by default. Use
`--skip-validation` only when intentionally inspecting bad data behavior.

Ingestion also writes JSON lineage artifacts:

```text
data/validation/market_bars/AAPL.json
data/metadata/market_bars/AAPL.json
```

## When Something Fails

1. Confirm the input data has the required columns:
   `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
2. Confirm dependencies are installed in the active environment.
3. Re-run with the smallest dataset that reproduces the issue.
4. Add a regression test before changing core accounting or signal behavior.
