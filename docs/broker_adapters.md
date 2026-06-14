# Broker Adapter Boundary v1

This project is a research and paper-trading system with no real-money broker
integration. Broker adapters separate strategy and execution semantics from
broker-specific APIs and state.

The legacy signal boundary is:

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

The semantic-target execution boundary is:

```text
approved risk target
  -> ExecutionPlan and append-only ExecutionEvent records
  -> LiveBrokerAdapter
  -> fake, local semantic-paper, or Alpaca paper client
  -> reconciliation-confirmed satisfaction
```

The repository can contact Alpaca paper through explicit legacy CLI/workflow
commands and through an opt-in semantic-target API. It cannot place real-money
trades.

## Current Implementation

`BrokerAdapter` defines the generic broker-facing methods.

`SignalExecutionBroker` extends that boundary with signal idempotency methods
needed by scheduled strategy execution.

`PaperBrokerAdapter` wraps the existing deterministic `PaperBroker` and
preserves the existing paper state and signal record formats.

`LiveBrokerAdapter` wraps live-shaped clients and writes broker-neutral order,
fill, and account artifacts. `FakeLiveBrokerClient` has no network access;
`AlpacaPaperBrokerClient` connects only to Alpaca paper; and the durable local
semantic-paper client simulates signed positions for lifecycle testing.

## Real-Money Broker Requirements

The live-shaped broker design is tracked in
[live_broker_adapter.md](live_broker_adapter.md). Before adding a live broker
for real money, define and test:

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
