# Activated Dry-Run Operator Rehearsal

## Purpose

This document records the June 14, 2026 local rehearsal of the first
semantic-target operator command:

```bash
quant dry-run activated-target
```

The command is limited to dry-run behavior. A dry-run calculates and records
what order would be needed, but it does not send an order to a broker and
cannot create a fill.

## Reviewed Synthetic Request

The rehearsal used temporary synthetic files under:

```text
/tmp/quant-activated-dry-run-operator-13dwhai2
```

The request described:

```text
symbol: AAPL
current position: 0 shares
approved target: +2 shares
reference price: $100
expected intended order: BUY 2 shares
expected notional: $200
```

The request referenced a passing base rehearsal, a passing
activation-consumption rehearsal, a time-limited dry-run authorization, and
the exact strategy, contributor, account, risk, and execution-policy inputs.

## Observed Result

The command was run twice with the exact same request and output paths.
Both runs reported:

```text
activation decision: allowed
workflow status: dry_run_observed
dry-run status: would_submit
intended order: BUY 2 shares
intended notional: $200
```

After both runs, durable output still contained exactly:

```text
1 preserved operator request
1 activation authorization
1 activation evaluation
1 activation consumption
1 orchestration record
1 execution plan
1 dry-run observation
```

This proves restart behavior did not duplicate the request, activation
consumption, plan, or observation.

## Safety Evidence

The command's activation and output directories contained:

```text
0 semantic-paper directories
0 order-artifact directories
0 fill-artifact directories
```

The prerequisite no-network rehearsals separately contain fake local-paper
evidence by design. Those files were inputs to the operator request and were
not created by the operator command.

The recurring Alpaca paper refresh scheduler was checked after the rehearsal
and reported `service not found`, meaning it remained unloaded.

No broker client was constructed, no network call was made, no broker order was
submitted, no fill occurred, and no runtime-clone state was changed.

## Verdict

The activated dry-run operator command passed its first local synthetic
rehearsal. It produced the expected no-submission evidence and remained
restart-safe.
