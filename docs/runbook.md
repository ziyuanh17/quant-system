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
data/paper/state/default.json
data/scheduler/latest/
```

Use `--state-path` to isolate separate paper accounts or experiments.
If the same actionable signal is processed again, the command records a skipped
signal instead of placing a duplicate paper order.

## Refresh Data Then Run Paper Signal

```bash
quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
```

This refreshes market data, writes validation and metadata artifacts, stops if
validation fails, then runs the scheduled paper-signal path. It writes a
workflow record under:

```text
data/workflows/paper-signal-refresh/
```

Use this path for recurring server runs once the provider and start date are
configured.

## Run The Service Wrapper

```bash
bash scripts/run_paper_signal_refresh.sh
```

Copy `.env.example` to `.env` to configure the wrapper. See
[deployment.md](deployment.md) for cron and systemd examples.

## Check Operational Health

```bash
quant ops health
```

The health command checks the latest scheduler run record, latest paper signal
record, persisted paper state, workflow lock, and wrapper log directory. It
returns a nonzero exit code only when the status is `failed`.

For a fuller daily check:

```bash
quant ops health --reconcile-state --initial-cash 100000
```

See [operations.md](operations.md) for status meanings and current limits.

## Inspect A Workflow Lock

```bash
cat data/locks/paper-signal-refresh.lock
```

The lock file should exist only while the refresh workflow is running. If it is
present after a crash, check whether a workflow process is still active before
removing it. A later run can replace the lock after the configured stale
timeout.

## Inspect Paper State

```bash
cat data/paper/state/default.json
cat data/paper/state/default.json.bak
```

Paper state saves use an atomic replace. The `.bak` file is the previous state
snapshot and is useful when debugging a bad run or interrupted process.

## Reconcile Paper State

```bash
quant paper reconcile-state --initial-cash 100000
```

This replays paper signal records and compares the expected cash, positions,
and processed signal keys against `data/paper/state/default.json`. It writes a
report under:

```text
data/paper/reconciliation/state.json
```

Use the same starting cash and optional starting position that were used when
the paper account was created.

## When Something Fails

1. Run `quant ops health` and read the issue codes.
2. Inspect the latest workflow record under `data/workflows/`.
3. If the failure mentions a lock, confirm whether another workflow is running.
4. Check the `Reconciliation:` line in `quant ops health`, or run
   `quant paper reconcile-state` for the standalone report.
5. Confirm the input data has the required columns:
   `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
6. Confirm dependencies are installed in the active environment.
7. Re-run with the smallest dataset that reproduces the issue.
8. Add a regression test before changing core accounting or signal behavior.
