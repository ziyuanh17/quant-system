# Semantic Target Architecture

## Purpose

The semantic-target architecture separates strategy intent from portfolio
construction, risk approval, and broker execution:

```text
strategy evaluation
  -> strategy target decision
  -> contributor-set portfolio aggregation
  -> risk target
  -> append-only execution lifecycle
  -> broker and reconciliation
```

The implemented stages define strategy-target contracts, immutable artifacts,
native target backtests, legacy-equivalence evidence, contributor ownership,
portfolio aggregation, independent risk decisions, and an isolated fake-broker
execution lifecycle. They do not change paper, dry-run, Alpaca, scheduler, or
runtime behavior.

## Strategy Targets

A strategy target describes desired exposure, not an order. A signed share
target has direct position meaning:

```text
-10 shares = short ten shares
  0 shares = flat
+10 shares = long ten shares
```

`StrategyTargetFrame` stores timestamp-aligned decimal research targets.
Fractional shares are valid in research. Operational whole-share validation is
separate and rejects fractional targets without rounding.

`StrategyTargetDecision` is an immutable target revision. It records strategy,
input-data, sizing-policy, effective-time, validity, and source-evidence
identity. A target's declared status is either `active` or `unavailable`.

Time-derived status is evaluated without rewriting the original decision:

```text
active
not_yet_effective
expired
stale
unavailable
```

`StrategyEvaluation` is a separate observation. A `no_change` evaluation
references the effective target decision and does not create a new revision.

## Immutable Research Artifacts

Research target artifacts are stored under:

```text
data/research/strategy-targets/
data/research/strategy-evaluations/
data/research/legacy-equivalence/
data/research/contributor-sets/
data/research/portfolio-targets/
data/research/risk-targets/
```

Artifacts are schema-versioned and written exclusively. Reusing an existing ID
fails instead of overwriting history. These artifacts are research evidence;
they never authorize operational execution.

## Native And Legacy Strategies

Native target strategies emit target frames directly. Price and feature target
strategies have separate protocols, matching the existing strategy boundaries.

Existing entry/exit strategies remain unchanged. Compatibility policies convert
their event signals into resolved targets:

- `fixed_shares_v1` carries an explicit share target between entry and exit.
- `legacy_available_cash_v1` investigates current VectorBT signal behavior by
  resolving its actual orders into a target history.

Legacy equivalence is evidence, not an assumption. Baseline signal simulation
and target-amount simulation are compared across trades and portfolio metrics.
If they differ, the existing legacy simulator remains authoritative and the
result is labeled non-equivalent.

## Portfolio Construction And Risk

`ContributorSet` is immutable, revisioned ownership configuration for one
symbol and unit. It pins each expected strategy ID and strategy version,
defines a freshness limit, and identifies the aggregation policy.

`sum_active_targets_v1` aggregation follows contributor-set order. It sums
signed targets only when every expected decision is active, fresh,
unit-compatible, and symbol-compatible. Missing, duplicate, unavailable,
not-yet-effective, expired, stale, or incompatible contributions produce an
explicit blocked portfolio target. Blocking never becomes a zero target.

`approve_or_reject_v1` risk evaluation persists an independent decision. It
either approves the exact aggregate or rejects it with reasons; it never
silently clamps, rounds, or resizes a target. Fractional research targets remain
valid at this layer.

## Fake-Broker Execution Lifecycle

The first execution implementation is isolated to the no-network fake broker.
It does not authorize or integrate with paper or live operational workflows.

One approved risk-target revision may atomically claim at most one immutable
`ExecutionPlan`. Claim, execution-plan, and client-order identities include
both the risk-target ID and revision, so later revisions do not collide. The
filesystem claim uses a lock plus an exclusive, deterministic path. Every
lifecycle transition is a separate append-only `ExecutionEvent`:

```text
planned
  -> submission_pending
  -> submitted
  -> filled | rejected | cancelled | ambiguous
  -> satisfied
```

`submission_pending` is persisted before broker interaction. A restart from
pending or ambiguous state must look up the deterministic client order ID.
Found orders recover broker state; not-found, unavailable, or conflicting
lookups block without automatic resubmission.

Direct submission responses, recovery lookups, and submitted-order refreshes
must match the planned client order ID, exact order request, and claimed broker
account identity. Accepted or partially filled orders remain `submitted` and
advance only through lookup-based refresh.

Lifecycle schema version 2 introduces revision-scoped plan identity,
broker-account binding, and durable broker-order identity. Version 1 lifecycle
artifacts fail closed and are not eligible for execution.

Given an execution artifact root, the lifecycle writes immutable records under:

```text
plans/
events/
recovery-evidence/
drift-observations/
```

Immediately before submission, the lifecycle revalidates strategy freshness,
contributor ownership, portfolio aggregation, risk approval, whole-share
capability, working orders, and current broker position. Satisfaction requires:

```text
broker position equals approved target
AND no unsettled orders exist
AND account-wide reconciliation passed
```

Failed satisfaction checks remain durable evidence and never trigger drift
repair. After satisfaction, `detect_only_v1` persists clear, detected, or
indeterminate drift observations without changing broker state.

## Future Stages

Later reviewed stages may migrate the lifecycle into local paper and dry-run
workflows. Alpaca paper integration requires a separate review.
