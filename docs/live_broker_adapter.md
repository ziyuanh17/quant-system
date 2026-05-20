# Live Broker Adapter Design v1

This project is still not a real-money trading system. This document defines
the design boundary for a future live broker adapter before any broker API,
credential, or real order submission code is added.

See [live_broker_api_research.md](live_broker_api_research.md) for the current
broker API/package research and first-integration recommendation.

The goal is to make live trading boring, explicit, auditable, and impossible by
accident.

## Non-Goals

This milestone does not add:

- broker credentials
- broker SDK dependencies
- network calls to a broker
- live order submission
- live fills
- live account mutation
- a CLI command that can place a real order

## Required Execution Shape

The future live path should follow this order:

```text
strategy signal
  -> typed order request
  -> trading safety check
  -> live broker adapter
  -> broker API request
  -> broker response record
  -> local audit artifact
  -> broker account snapshot
  -> reconciliation report
```

The adapter must sit behind the existing broker boundary. Strategy code should
not import a broker SDK, read credentials, know provider-specific order IDs, or
handle broker-specific rejection messages directly.

## Adapter Contract

A future live adapter should provide these capabilities:

- validate that `TradingSafetyCheck` is allowed and has `mode=live`
- submit a typed market order request
- return a typed live order record for accepted, rejected, partially filled,
  filled, cancelled, and unknown broker states
- read a broker account snapshot without placing an order
- read open orders from the broker
- read recent fills or executions from the broker
- map broker-specific symbols into the project symbol format
- expose broker name, account identifier, and environment in audit records

The adapter should not own strategy decisions, risk policy, scheduling,
feature generation, or dashboard publishing. Those remain outside the broker
integration.

## Credential Boundary

Credential loading must happen only inside a small broker-client factory, after
the live safety check passes.

Rules:

- credentials are never stored in repo files
- `.env.example` may show variable names but never real values
- credentials are never written to logs, workflow records, dashboard status, or
  audit artifacts
- the adapter records a sanitized account identifier, not full account secrets
- missing credentials fail before any order request is built
- test fixtures use fake clients, never real broker sandboxes by default

Expected future variables should be broker-specific and explicit, for example:

```text
QUANT_LIVE_BROKER=example
QUANT_LIVE_BROKER_ENV=sandbox
QUANT_LIVE_ACCOUNT_ID=...
QUANT_LIVE_API_KEY=...
QUANT_LIVE_API_SECRET=...
```

The existing `QUANT_BROKER` safety variable identifies the intended broker for
the safety gate. It should not become a credential container.

## Safety Gates

Every future live-capable entry point must call `assert_trading_allowed` before
constructing a live broker client.

Required live inputs remain:

- `QUANT_TRADING_MODE=live`
- `QUANT_LIVE_TRADING_ENABLED=true`
- `QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK`
- positive `QUANT_MAX_ORDER_NOTIONAL`
- non-empty `QUANT_BROKER`

Additional live adapter checks should include:

- requested broker matches configured broker
- order notional is less than or equal to the configured maximum
- symbol is in the configured tradable universe
- order side and quantity are valid for the account
- market session policy allows submission now
- account buying power or position availability is sufficient
- duplicate client order ID has not already been submitted

Safety checks must fail closed. A missing setting should block the order.

## Idempotency

Live order idempotency must survive process restarts.

Each live order attempt should have:

- signal idempotency key
- local client order ID
- broker order ID when one exists
- strategy name
- symbol
- side
- quantity
- signal date
- created timestamp

The system must check local audit records before submitting a live order. If the
local record says the same client order ID was already accepted by the broker,
the command must not submit again.

If local state is missing but the broker has an open or filled order with the
same client order ID, reconciliation should restore or flag the local record
instead of submitting a duplicate.

## Audit Artifacts

Live trading needs an audit trail before it needs automation.

Recommended artifact paths:

```text
data/live/orders/
data/live/fills/
data/live/account_snapshots/
data/live/reconciliation/
data/workflows/live-signal-refresh/
data/locks/live-signal-refresh.lock
```

Live order records should include:

- local record ID
- client order ID
- broker order ID, if known
- broker name
- sanitized account ID
- broker environment, such as `sandbox` or `production`
- original typed `OrderRequest`
- requested market price or reference price
- submitted quantity
- submitted side
- requested notional
- safety check result
- broker status
- broker rejection reason, if rejected
- timestamps for local creation, submission, broker update, and local write
- raw broker response hash or reference path, not secrets

The first implementation should prefer append-only JSON artifacts. Later, these
can move behind the same storage abstraction style used for market data.

## Broker State Reconciliation

Live reconciliation must compare local audit artifacts against broker truth.

At minimum, a reconciliation report should compare:

- local accepted orders vs broker open orders
- local filled records vs broker executions
- local positions vs broker positions
- local cash or buying-power snapshot vs broker account snapshot
- local client order IDs vs broker order IDs

Reconciliation must be read-only. It should never place orders, cancel orders,
or mutate broker state. Any drift should produce a report and a failed or
degraded health status.

## CLI And Workflow Boundaries

Future live commands should be separate from paper and dry-run commands.

Acceptable shape:

```text
quant live order --...
quant live reconcile --...
quant workflow live-signal-refresh --...
```

Unsafe shape:

```text
quant paper ... --live
quant dry-run ... --submit
```

Routine paper and dry-run jobs must never become live-capable by toggling one
small flag. A live command should require a distinct command namespace,
explicit safety config, and live-specific output directories.

## Implementation Order

Build in this order:

1. Add typed live order, fill, account snapshot, and reconciliation models.
2. Add append-only live artifact writers.
3. Add fake live broker client tests with no network access.
4. Add a live adapter against the fake client only.
5. Add live reconciliation against fake broker snapshots.
6. Add CLI commands that are blocked by safety gates and fake-client tests.
7. Only then evaluate a real broker SDK integration.

Typed live audit models, artifact writers, a no-network fake live broker
client, a fake-backed live adapter, fake live reconciliation, and safety-gated
fake live CLI commands now exist. The next milestone should design the Alpaca
paper adapter boundary before adding any real broker SDK dependency.
