# Broker Adapter Boundary v1

This project is still a paper-trading system. Broker Adapter Boundary v1 exists
to make the future real-money integration safer by separating strategy signal
logic from broker-specific execution details.

The boundary is:

```text
strategy signal
  -> SignalExecutionBroker protocol
  -> PaperBrokerAdapter
  -> PaperBroker
```

## Why This Boundary Exists

Real broker integrations have different order IDs, account snapshots, rejected
order behavior, rate limits, authentication, market hours, and partial-fill
semantics. Strategy code should not need to know those details.

The adapter boundary keeps the core system asking for a small set of behaviors:

- submit a market order
- read an account snapshot
- check whether a signal idempotency key was already processed
- mark a signal idempotency key as processed

The current adapter only wraps the local paper broker. It does not call any
external broker API and cannot place real trades.

## Current Implementation

`BrokerAdapter` defines the generic broker-facing methods.

`SignalExecutionBroker` extends that boundary with signal idempotency methods
needed by scheduled strategy execution.

`PaperBrokerAdapter` wraps the existing deterministic `PaperBroker` and
preserves the existing paper state and signal record formats.

## Future Live Broker Requirements

The live broker design is now tracked in
[live_broker_adapter.md](live_broker_adapter.md). Before adding a live broker
adapter, define and test:

- broker credential loading rules
- market-hours and asset-universe checks
- order idempotency that survives process restarts
- partial-fill and cancellation behavior
- account snapshot reconciliation
- maximum order size and maximum daily-loss guardrails
- dry-run mode for every live adapter command

Live trading should remain impossible by default. A real adapter should require
clear configuration and separate commands so routine paper jobs cannot
accidentally send real orders.

See [trading_safety.md](trading_safety.md) for the first live-trading safety
gate implementation.
