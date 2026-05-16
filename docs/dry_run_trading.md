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
