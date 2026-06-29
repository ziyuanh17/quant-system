# Semantic-Target Reversal Lifecycle Design

This document designs explicit close/open lifecycle support for semantic-target
transitions that cross zero.

The immediate trigger was the June 29, 2026 Alpaca paper test. The account held
`AAPL=-1`, the reviewed risk target was `AAPL=+2`, and the current single-order
lifecycle planned one net `BUY 3 AAPL`. Alpaca paper returned an
insufficient-quantity error, and the system correctly preserved a durable
`ambiguous` outcome without retrying.

## Problem

A cross-zero transition is not just a larger ordinary order.

These are semantically different:

```text
same-side increase:  +1 -> +3  means open/increase long by 2
flatten long:        +1 ->  0  means close long by 1
reversal:            -1 -> +2  means close short by 1, then open long by 2
```

The current `ExecutionPlan` model stores one `order_request` and one
deterministic client order ID. That is sufficient for same-side changes and
flattening, but it does not preserve the close/open boundary required for
reversals.

## Required Semantics

For a cross-zero reversal, the execution lifecycle must distinguish two legs:

```text
short -> long:
  close_short: BUY abs(current_quantity)
  open_long:   BUY target_quantity

long -> short:
  close_long:  SELL current_quantity
  open_short:  SELL abs(target_quantity)
```

Even when both legs use the same broker side, they are not equivalent to one
net order in the infrastructure:

- they have different risk meaning;
- they may have different broker constraints;
- they need separate client order IDs;
- failure of the close leg must block the open leg;
- reconciliation must confirm the intermediate flattening before opening the
  opposite exposure.

## V1 Implementation Boundary

The first implementation should stay source-side and broker-free:

- add a deterministic transition planner that returns one or two intended
  order legs;
- keep the current Alpaca paper guard that blocks cross-zero reversals before
  broker submission;
- test long increase, long flatten, short cover, short increase, and both
  reversal directions;
- do not change `ExecutionPlan` persistence yet;
- do not expose broker-connected reversal execution yet.

This gives the system a tested semantic contract before changing durable
execution artifacts.

## Future Durable Model

The later order-capable implementation should introduce a new schema version or
a separate durable object such as:

```yaml
execution_transition_plan:
  schema_version: 1
  execution_plan_id: execution-risk-1-r1
  current_quantity: -1
  target_quantity: 2
  legs:
    - leg_id: close-short
      leg_index: 1
      semantic: close_short
      order:
        side: buy
        quantity: 1
      required_start_quantity: -1
      required_end_quantity: 0
    - leg_id: open-long
      leg_index: 2
      semantic: open_long
      order:
        side: buy
        quantity: 2
      required_start_quantity: 0
      required_end_quantity: 2
```

Each leg needs:

- deterministic client order ID;
- append-only lifecycle events;
- broker lookup/recovery evidence;
- reconciliation evidence before advancing to the next leg;
- explicit blocked/ambiguous handling.

## Risk Rules

For reversals, risk must check both:

- the current leg order; and
- the resulting portfolio state after that leg.

The open leg must not run unless the close leg is reconciled. For example,
`-1 -> +2` requires short-cover confirmation at `0` before the long-opening
leg can submit. If reconciliation is unavailable, divergent, or stale, the
transition blocks.

## Operational Policy

Until durable multi-leg lifecycle support exists:

- Alpaca paper cross-zero transitions must block before broker submission;
- local fake-broker tests may exercise the transition planner only;
- same-side and flattening paper tests may proceed under the existing
  one-request gate;
- no automated retry may turn an ambiguous reversal into another broker order.

This preserves restart safety and avoids disguising a semantic reversal as a
single arithmetic delta.
