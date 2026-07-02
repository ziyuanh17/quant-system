# Semantic-Target Alpaca Paper Fake-Client Transition Rehearsal

Date: 2026-07-01

Status: In review

## Purpose

This document records the source-level fake-client rehearsal for Alpaca-shaped
semantic-target transition execution.

This stage is broker-free. It does not source credentials, contact Alpaca,
submit real Alpaca paper orders, touch the runtime clone, load launchd, add a
CLI command, or enable scheduler behavior.

## What Changed

The generic multi-leg transition runner now handles restart recovery for
individual transition legs:

- a leg in `submission_pending` or `ambiguous` is recovered by deterministic
  client order ID;
- a found order moves the leg back to `submitted` and then to a terminal leg
  status if broker truth is terminal;
- a not-found, unavailable, or conflicting lookup blocks the leg without
  automatic resubmission;
- a submitted leg is refreshed by deterministic client order ID rather than
  resubmitted;
- recovered orders and fills are materialized into local order/fill evidence
  through `LiveBrokerAdapter.orders_by_client_order_id(...)`.

This moves the transition lifecycle closer to the approved Alpaca paper design
without opening the real Alpaca transition doorway.

## Rehearsed Scenarios

The new tests use the real `AlpacaPaperBrokerClient` wrapper with a fake
Alpaca-shaped trading client and the real generic multi-leg transition runner.

### Crash After Broker Acceptance

Scenario:

```text
initial position: AAPL=-1
target position:  AAPL=+2
transition legs:  BUY 1 close_short, then BUY 2 open_long
```

The first run delegates the first leg to the Alpaca-shaped adapter and then
raises an exception after the fake broker accepted the order. The first run
therefore records:

```text
leg 1: ambiguous
leg 2: planned
```

The second run recovers leg 1 by Alpaca client order ID, reconciles the
intermediate flat position, submits leg 2, reconciles the final long position,
and finishes with:

```text
leg 1: reconciled
leg 2: reconciled
final position: AAPL=+2
```

The fake Alpaca client records exactly one lookup for the first leg client
order ID and exactly two submitted client order IDs total, proving the first leg
was not duplicated on restart.

### Ambiguous Lookup Blocks

The second rehearsal manually creates an ambiguous leg with no durable broker
context. The runner attempts recovery by client order ID, the Alpaca-shaped
adapter reports lookup unavailable, and the leg becomes blocked:

```text
leg 1: blocked
leg 2: planned
submitted orders: 0
```

This proves an ambiguous leg does not turn into a fresh submission when broker
recovery evidence is missing.

## Current Boundary

The real `quant semantic-target alpaca-paper` command still blocks cross-zero
transitions before Alpaca submission. This stage only strengthens the shared
transition lifecycle and proves that the Alpaca paper client shape can support
per-leg recovery.

Before any real Alpaca paper reversal test, the project still needs a reviewed
Alpaca transition evidence verifier and a separate operational runbook/rehearsal
for one market-session request.

## Verification

Focused verification passed:

```text
.venv/bin/ruff check tests/test_alpaca_paper_client.py src/quant/execution/target_lifecycle.py src/quant/execution/live_broker.py
.venv/bin/python -m pytest tests/test_alpaca_paper_client.py tests/test_execution_lifecycle.py -q
```
