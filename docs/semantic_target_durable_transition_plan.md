# Semantic-Target Durable Transition Plan

This stage adds broker-free durable artifacts for semantic target transitions.

It does not submit orders, change broker state, enable Alpaca reversal
execution, or replace the existing single-order `ExecutionPlan`.

## Implemented Contract

The source now defines:

- `ExecutionTransitionPlan`
- `ExecutionTransitionLeg`

An `ExecutionTransitionPlan` belongs to one existing `ExecutionPlan` and
records the semantic quantity path from current broker position to approved
target quantity.

Each leg records:

- deterministic `leg_id`;
- contiguous `leg_index`;
- semantic label such as `close_short` or `open_long`;
- broker-neutral `OrderRequest`;
- required start quantity;
- required end quantity;
- deterministic per-leg client order ID.

The validator enforces:

- no legs when current quantity already equals target quantity;
- at least one leg when current and target differ;
- contiguous leg indexes;
- each leg starts where the previous leg ended;
- final leg reaches the target quantity;
- leg order side and quantity exactly match the leg delta;
- leg symbols match the parent transition plan;
- per-leg client order IDs are unique.

## Persistence

Transition plans are immutable JSON artifacts under:

```text
<artifact-root>/transition-plans/<execution-plan-id>.json
```

APIs:

```text
build_execution_transition_plan(...)
write_execution_transition_plan(...)
load_execution_transition_plan(...)
execution_transition_plan_path(...)
```

The write path is exclusive. Rewriting the same transition plan path raises
`FileExistsError`.

## Reversal Example

For an existing paper position:

```text
current: AAPL = -1
target:  AAPL = +2
```

The durable transition plan records:

```text
leg 1: close_short BUY 1, required -1 -> 0
leg 2: open_long   BUY 2, required  0 -> 2
```

The two legs intentionally have separate client order IDs:

```text
target-risk-1-r1-leg-1
target-risk-1-r1-leg-2
```

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_execution_lifecycle.py
38 passed

.venv/bin/ruff check src/quant/models/execution_lifecycle.py src/quant/models/__init__.py src/quant/execution/lifecycle_artifacts.py src/quant/execution/target_lifecycle.py src/quant/execution/__init__.py tests/test_execution_lifecycle.py
All checks passed!
```

The focused tests prove:

- short-to-long reversal records `close_short` then `open_long`;
- both legs have correct order quantities and broker side;
- per-leg client order IDs are deterministic and distinct;
- transition plan writes are immutable;
- old schema versions fail validation;
- already-satisfied transitions persist with no legs.

## Remaining Boundary

This is not yet order-capable multi-leg execution. Alpaca paper still blocks
cross-zero reversals before broker submission.

The next stage must add per-leg lifecycle events, recovery evidence,
reconciliation gates, and fail-closed advancement rules before any broker path
can submit reversal legs.
