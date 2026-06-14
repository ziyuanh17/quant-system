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
portfolio aggregation, independent risk decisions, a restart-safe execution
lifecycle, an opt-in local semantic-target dry-run observation, durable local
semantic paper, and an explicitly gated Alpaca paper API workflow. They do not
change the legacy signal dry-run, legacy signal paper, CLI, scheduler, or
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

## Execution Lifecycle

The lifecycle was first proven against the no-network fake broker and is now
reused by semantic dry-run, durable local semantic paper, and the explicitly
gated Alpaca paper API. It does not itself authorize operational execution.

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
dry-run-observations/
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

## Local Semantic-Target Dry Run

An opt-in read-only dry-run evaluator revalidates a claimed execution plan
against a caller-supplied local account snapshot. It uses the same strategy,
portfolio, risk, whole-share, account-identity, position, and working-order
checks as pre-submission validation, but requires an allowed `dry_run` safety
check and never receives a broker submission capability.

Each plan may write one deterministic, immutable `ExecutionDryRunObservation`:

```text
would_submit
already_satisfied
blocked
```

The observation records the intended order and notional, or durable blocking
reasons. It deliberately leaves the execution plan in `planned`; dry-run
evidence never claims that an order was submitted, filled, or reconciled.
Re-running the same plan cannot overwrite or create a second observation.
The existing signal-based dry-run CLI and scheduler workflow remain unchanged.

## Local Semantic Paper

Semantic paper is a separate, durable, live-shaped local broker. It does not
reuse or modify the legacy signal-oriented `PaperBroker`, which remains
long-only and keeps signal idempotency state.

The semantic-paper client supports signed positions, covers, and reversals. It
persists broker state atomically before returning from submission and stores
orders and fills by deterministic client-order identity. A restart after an
ambiguous response can therefore recover the existing local paper order without
resubmitting it.

The opt-in workflow runs:

```text
claim or recover execution plan
  -> require allowed paper safety mode
  -> submit or recover durable local paper order
  -> write live-shaped order, fill, and account artifacts
  -> persist immutable reconciliation evidence against durable paper state
  -> mark target satisfied only after reconciliation passes
```

Legacy paper commands and scheduled workflows remain unchanged. Alpaca paper
integration is available only through a separately gated API workflow.

## Alpaca Semantic-Target Paper Integration

The opt-in Alpaca semantic-target workflow reuses the same execution lifecycle
and immutable reconciliation requirements. It is not connected to a CLI,
scheduler, or runtime service.

Activation requires both:

```text
alpaca_submission_enabled = true
allowed live-shaped safety config with broker_name = alpaca-paper
```

Before a planned order may submit, the workflow checks maximum order notional,
projected account exposure, buying power, asset tradability, and short-borrow
availability. Pending or ambiguous submissions are recovered only by the
deterministic client order ID. The Alpaca client must have durable plan context
before lookup so the recovered broker order can be checked against the exact
planned request.

The workflow writes live-shaped order, fill, snapshot, lifecycle, recovery, and
immutable reconciliation artifacts. A filled order becomes `satisfied` only
after account-wide reconciliation passes. Operational CLI and scheduler
activation remain a later, separately approved stage.
