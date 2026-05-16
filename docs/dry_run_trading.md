# Dry-Run Broker Adapter v1

Dry-run trading rehearses the live-broker path without submitting an order,
creating a fill, or mutating account state.

The first dry-run path is:

```text
quant dry-run order
  -> TradingSafetyConfig(mode=dry_run)
  -> DryRunBrokerAdapter
  -> DryRunOrderRecord
```

Strategy signals can also route into the dry-run path:

```text
quant dry-run signal
  -> MomentumStrategy
  -> latest signal decision
  -> DryRunBrokerAdapter
  -> DryRunOrderRecord for buy/sell signals
```

The same path can run inside the scheduler:

```text
quant schedule dry-run-signal
  -> SchedulerRunner
  -> quant dry-run signal behavior
  -> scheduler run records
```

## Run One Dry-Run Order

```bash
quant dry-run order \
  --symbol AAPL \
  --side buy \
  --quantity 1 \
  --price 100 \
  --broker-name dry-run
```

This writes:

```text
data/dry_run/orders/<record-id>.json
```

## Run The Latest Strategy Signal

```bash
quant dry-run signal \
  --strategy momentum \
  --data data/sample_prices.csv \
  --symbol AAPL \
  --quantity 1 \
  --broker-name dry-run
```

Buy and sell signals write a would-submit order record under:

```text
data/dry_run/orders/
```

Hold signals print `Dry-run order: none` and do not write an order record.

## Schedule Dry-Run Signals

```bash
quant schedule dry-run-signal \
  --strategy momentum \
  --data data/sample_prices.csv \
  --symbol AAPL \
  --quantity 1 \
  --iterations 1
```

This writes scheduler run records under:

```text
data/scheduler/dry-run/
```

Buy and sell signals also write dry-run order records under:

```text
data/dry_run/orders/
```

Hold signals write a scheduler run record with no order artifact.

## Compare Paper And Dry-Run Records

```bash
quant dry-run compare-paper
```

By default, this compares the latest paper signal record under
`data/paper/signals/` with the latest dry-run order record under
`data/dry_run/orders/`, then writes:

```text
data/dry_run/comparison/latest.json
```

The comparison checks order presence, side, symbol, quantity, and market price.
Paper hold or skipped signals should have no matching dry-run order. A mismatch
returns a nonzero exit code so scheduled checks can catch divergence before any
live broker adapter exists.

Operational health can surface the latest comparison status:

```bash
quant ops health --check-comparison
```

## Run The Dry-Run Refresh Workflow

```bash
quant workflow dry-run-refresh \
  --symbol AAPL \
  --start 2024-01-01 \
  --quantity 1
```

This is the composed server-style path for dry-run trading. It refreshes and
validates market data, runs the scheduled dry-run signal loop, compares the
latest paper signal with the latest dry-run order when paper signal artifacts
exist, and writes a workflow record under:

```text
data/workflows/dry-run-refresh/
```

The workflow can also publish dashboard health status:

```bash
quant workflow dry-run-refresh \
  --symbol AAPL \
  --start 2024-01-01 \
  --quantity 1 \
  --publish-status-path site/status.json
```

It still stops before broker submission. It does not create fills or mutate
paper account state.

For recurring local or server runs, prefer the wrapper:

```bash
bash scripts/run_dry_run_refresh.sh
```

The wrapper reads `.env`, uses the `QUANT_DRY_RUN_*` output settings, and writes
a timestamped log under `logs/`.

The record says what would have been submitted to a broker:

- symbol
- side
- quantity
- market price
- notional
- broker name
- safety check result

It intentionally does not include:

- fill
- paper account snapshot
- cash mutation
- position mutation
- external broker response

## Difference From Paper Trading

Paper trading simulates a broker and mutates fake account state. Dry-run
trading records the intended broker request and stops before execution.

Use paper mode to ask:

```text
What would my simulated account look like after this signal?
```

Use dry-run mode to ask:

```text
What order would the live-shaped path attempt to submit?
```

Dry-run mode still cannot place real orders.
