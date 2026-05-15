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
