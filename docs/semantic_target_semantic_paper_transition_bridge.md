# Semantic-Target Semantic-Paper Transition Bridge

This stage adds a local semantic-paper bridge for durable transition plans.

It is still broker-free beyond the local on-disk semantic-paper broker. It does
not call Alpaca, does not change runtime-clone state, does not expose recurring
scheduling, and does not enable Alpaca paper reversal execution.

## Design Reason

The previous semantic-paper workflow could move from short to long with one net
order, such as:

```text
AAPL -2 -> AAPL +3 = BUY 5
```

That is acceptable for a simple local simulator, but it does not rehearse the
execution shape needed for a mature target system. A cross-zero target change
has two different meanings:

```text
close the short: BUY 2
open the long:  BUY 3
```

Those legs have different risk, recovery, and reconciliation meaning. This
bridge keeps the old semantic-paper workflow unchanged, then adds a separate
path that uses the durable transition-plan lifecycle.

## Implemented Contract

The source now defines:

- `SemanticPaperTransitionRunResult`
- `run_semantic_target_paper_transition(...)`

The bridge:

1. creates or loads the durable `ExecutionPlan`;
2. creates or loads the immutable `ExecutionTransitionPlan`;
3. runs the existing pre-submission validation gate with paper safety mode;
4. executes transition legs through `SemanticPaperBrokerAdapter`;
5. writes live-shaped local paper orders, fills, snapshots, reconciliation
   reports, and append-only leg events;
6. requires every prior leg to be reconciled before the next leg starts;
7. skips already reconciled legs on restart, so repeated runs do not duplicate
   local paper orders;
8. marks the parent execution plan `satisfied` only after all transition legs
   reconcile.

## Example

Starting from a local paper short:

```text
AAPL = -2
```

and targeting:

```text
AAPL = +3
```

the bridge writes a transition plan with:

```text
leg 1: close_short BUY 2, required -2 -> 0
leg 2: open_long   BUY 3, required  0 -> 3
```

The old `run_semantic_target_paper(...)` path remains unchanged and still uses
the single-order lifecycle until a later migration is reviewed.

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_semantic_paper.py tests/test_execution_lifecycle.py
57 passed

.venv/bin/ruff check src/quant/execution/target_lifecycle.py src/quant/execution/target_paper.py src/quant/execution/__init__.py tests/test_semantic_paper.py tests/test_execution_lifecycle.py
All checks passed!
```

The tests prove:

- the existing semantic-paper workflow still handles a reversal as one net
  order;
- the new transition bridge handles the same reversal as `close_short` then
  `open_long`;
- every transition leg reaches `reconciled`;
- the final local paper state reaches the target position;
- rerunning after satisfaction creates no duplicate local paper orders or
  fills.

## Remaining Boundary

This bridge is not an Alpaca paper bridge. The next stage should design a
reviewed operator or rehearsal boundary for invoking this local transition path
from a checked request artifact. Alpaca reversal exposure remains blocked until
fresh paper-specific evidence proves the same lifecycle, recovery, and
reconciliation behavior against the broker.
