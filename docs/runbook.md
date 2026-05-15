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

## Run A Scheduled Paper Task

```bash
quant schedule paper-order --symbol AAPL --side buy --quantity 1 --price 100 --iterations 1
```

This command writes:

```text
data/paper/scheduled/
data/scheduler/latest/
```

Use `--iterations` and `--interval-seconds` for a finite repeated run. Keep
finite loops as the default until the system has explicit service supervision,
idempotency, and alerting.

## Run A Scheduled Paper Signal

```bash
quant schedule paper-signal --strategy momentum --data data/sample_prices.csv --symbol AAPL --quantity 1 --iterations 1
```

This generates the latest strategy signal from the input data, turns that
signal into a paper-trading decision, and writes:

```text
data/paper/signals/
data/scheduler/latest/
```

## When Something Fails

1. Confirm the input data has the required columns:
   `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
2. Confirm dependencies are installed in the active environment.
3. Re-run with the smallest dataset that reproduces the issue.
4. Add a regression test before changing core accounting or signal behavior.
