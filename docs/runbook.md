# Runbook

## Local Backtest

```bash
quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
```

## When Something Fails

1. Confirm the input data has the required columns:
   `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
2. Confirm dependencies are installed in the active environment.
3. Re-run with the smallest dataset that reproduces the issue.
4. Add a regression test before changing core accounting or signal behavior.

