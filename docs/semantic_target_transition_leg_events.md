# Semantic-Target Transition Leg Events

This stage adds append-only lifecycle events for individual transition-plan
legs.

It remains broker-free. It does not submit orders, recover broker orders,
perform reconciliation, or enable Alpaca paper reversal execution.

## Implemented Contract

The source now defines:

- `ExecutionLegStatus`
- `ExecutionLegEvent`

Leg statuses:

```text
planned
submission_pending
submitted
filled
rejected
cancelled
ambiguous
blocked
reconciled
```

Allowed transitions:

```text
planned -> submission_pending | blocked
submission_pending -> submitted | ambiguous | blocked
submitted -> filled | rejected | cancelled | ambiguous
ambiguous -> submitted | blocked
filled -> reconciled
```

Terminal states:

```text
rejected
cancelled
blocked
reconciled
```

## Persistence

Leg events are immutable JSON artifacts under:

```text
<artifact-root>/leg-events/<transition-plan-id>/<leg-id>/<sequence>.json
```

APIs:

```text
append_execution_leg_event(...)
load_execution_leg_events(...)
current_execution_leg_status(...)
```

The append helper validates:

- the leg exists in the transition plan;
- timestamps are monotonic;
- event sequences are contiguous;
- status transitions are allowed;
- submitted events include exactly one broker order ID;
- later events cannot reference a different broker order ID.

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_execution_lifecycle.py
42 passed

.venv/bin/ruff check src/quant/models/execution_lifecycle.py src/quant/models/__init__.py src/quant/execution/lifecycle_artifacts.py src/quant/execution/__init__.py tests/test_execution_lifecycle.py
All checks passed!
```

The tests prove:

- a leg can move from planned through submission, fill, and reconciliation;
- current leg status derives from append-only events;
- invalid direct transitions fail;
- broker order ID changes are rejected before persistence;
- tampered event chains fail validation.

## Remaining Boundary

This is not yet a multi-leg execution runner. The next stage must connect these
events to broker-free fake execution and reconciliation gates, then prove:

- leg 2 cannot start until leg 1 is reconciled;
- blocked or ambiguous leg 1 prevents leg 2;
- restart recovery resumes from the durable leg status without duplicate
  orders.
