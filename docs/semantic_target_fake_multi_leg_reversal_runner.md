# Semantic-Target Fake Multi-Leg Reversal Runner

This stage adds a broker-free runner for semantic target transition plans.

It uses the no-network `FakeLiveBrokerClient` only. It does not call Alpaca,
does not change runtime-clone state, does not expose scheduler behavior, and
does not enable semantic-target reversal execution in Alpaca paper.

## Implemented Contract

The source now defines:

- `MultiLegTransitionRunResult`
- `run_fake_multi_leg_transition(...)`

The runner consumes an existing `ExecutionTransitionPlan` and processes each
leg in order. For every leg, it:

1. checks that all prior legs are already `reconciled`;
2. skips legs already marked `reconciled` so restart does not duplicate them;
3. checks that the fake broker position equals the leg's required start
   quantity;
4. checks that there are no working broker orders;
5. records `submission_pending` before broker interaction;
6. submits one fake market order with the leg's deterministic client order ID;
7. records submitted and terminal order status events;
8. writes live-shaped fake order, fill, snapshot, and reconciliation artifacts;
9. records `reconciled` only after account-wide reconciliation passes and the
   broker position equals the leg's required end quantity.

If a leg is blocked before broker submission, later legs do not start. If a leg
is filled but not reconciled, it remains `filled`; that is deliberate because a
fill happened, but the position has not yet been confirmed as satisfying the
transition.

## Fake Broker Coverage

The fake live broker now handles BUY orders that cover existing short
positions. This lets the broker-free test path rehearse a short-to-long
transition:

```text
start:  AAPL = -1
leg 1:  BUY 1  close_short  -1 -> 0
leg 2:  BUY 2  open_long     0 -> +2
finish: AAPL = +2
```

The fake broker still does not broadly enable short opening through the runner
as an operational capability. Alpaca paper reversal submission remains blocked
until a later reviewed stage connects this lifecycle to a broker path with
paper-specific evidence.

## Persistence

The runner reuses existing live-shaped artifact directories supplied by the
caller:

```text
orders/
fills/
snapshots/
reconciliations/<transition-plan-id>/<leg-id>/
leg-events/<transition-plan-id>/<leg-id>/
```

These artifacts are useful because they prove the same evidence shape that a
future broker adapter must satisfy, while staying entirely offline.

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_fake_live_broker.py tests/test_execution_lifecycle.py
53 passed
```

The tests prove:

- fake BUY orders can cover a short position and can cover then open long;
- a short-to-long transition reconciles leg 1 before starting leg 2;
- the final fake broker position reaches the approved target;
- rerunning after reconciliation skips completed legs and creates no duplicate
  orders or fills;
- a broker position mismatch blocks before any fake order is submitted.

## Remaining Boundary

This is still not Alpaca paper reversal execution. The next reviewed stages
must connect transition-plan evidence to the semantic paper and Alpaca paper
paths gradually, with fresh broker truth, paper-specific safety gates, and
restart/recovery evidence before any broker-connected reversal leg can be
submitted.
