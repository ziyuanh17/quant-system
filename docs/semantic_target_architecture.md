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

## Controlled Semantic-Target Orchestration

The API-only orchestration boundary composes the implemented target stages
without connecting them to a CLI, scheduler, runtime clone, or Alpaca:

```text
strategy decisions and evaluations
  -> persist immutable contributor and strategy artifacts
  -> aggregate and persist portfolio target
  -> evaluate and persist risk target
  -> stop durably when blocked, rejected, or operationally incompatible
  -> otherwise run semantic dry-run or durable local semantic paper
  -> persist one immutable orchestration record
```

Each orchestration ID is bound to a fingerprint of the complete run inputs,
including target inputs, policies, safety check, reference price, evaluation
time, and mode-specific account or initial-state inputs. Restarting the same
run verifies that identity and returns its existing durable result. A crash
before the orchestration record is written re-enters the underlying
restart-safe execution lifecycle. Fractional research targets remain preserved
in portfolio and risk artifacts but produce an operationally blocked workflow
without rounding or an execution plan.

## Local Orchestration Rehearsal

The no-network local rehearsal is the review gate after controlled
orchestration and before any operational exposure. It runs isolated synthetic
scenarios for:

```text
eligible dry-run
dry-run restart idempotency
stale-target blocking
working-order blocking
risk rejection
fractional-target operational blocking
local semantic-paper restart idempotency
reconciliation-failure satisfaction blocking across restart
```

It writes one immutable `SemanticTargetRehearsalReport` plus the complete
orchestration evidence for each scenario. Re-reading an existing report
verifies every linked orchestration record and fails if evidence is missing or
no longer matches the summary. The rehearsal has no Alpaca client, network
access, CLI command, scheduler entry point, or runtime-clone behavior.

The reconciliation-failure scenario uses an explicitly identified,
fingerprinted reconciliation runner only in local semantic paper. The
fingerprint binds both its declared version ID and callable identity. It first
performs normal reconciliation, then injects one deterministic failing
difference. The order still fills exactly once, but the lifecycle remains
durably `filled` rather than becoming `satisfied`; restarting the orchestration
does not submit another order or create another fill. Broker-connected and
Alpaca reconciliation paths do not receive this injection boundary.

## Operational Activation Gate

The API-only activation gate separates durable human authorization from
capability exposure. An immutable `SemanticTargetActivationAuthorization`
binds:

```text
allowed scope and validity interval
  -> orchestration policy version
  -> rehearsal policy version
  -> exact rehearsal identity and report SHA-256
  -> operator identity, reason, and evidence references
```

Each request produces an immutable `SemanticTargetActivationEvaluation`.
Missing, changed, failed, or unverifiable rehearsal evidence; unsupported
policies; unauthorized scope; and not-yet-effective or expired authorization
all produce durable blocked evidence. Reusing an evaluation ID with different
inputs fails.

Gate v1 supports only `dry_run` and `semantic_paper`. It deliberately blocks
`alpaca_paper`, and it has no CLI, scheduler, runtime-clone, broker, or workflow
invocation boundary. A later reviewed exposure stage must consume an allowed
evaluation and revalidate it before doing any operational work.

## Activated Local Orchestration

The API-only activated wrappers consume the gate for dry-run and local
semantic paper without exposing either path operationally:

```text
authorization and exact rehearsal evidence
  -> immediate activation re-evaluation
  -> atomic one-evaluation-to-one-orchestration consumption claim
  -> allowed: controlled dry-run or local semantic-paper orchestration
  -> blocked: durable evaluation and consumption evidence, then stop
```

The immutable consumption artifact binds the activation evaluation ID, scope,
and orchestration ID. Concurrent or later attempts to use the same evaluation
for another orchestration fail closed. Allowed consumption evidence is included
in portfolio and risk target evidence and therefore in orchestration identity.

The original controlled orchestration APIs remain available without activation
so the local rehearsal can construct the evidence required by the gate.
Activated wrappers are the reviewed consumer boundary. They still have no CLI,
Alpaca, scheduler, runtime-clone, or server entry point.

## Activation-Consumption Rehearsal

Activation consumption is verified by a separate second-layer no-network
rehearsal. It cannot safely be part of the base orchestration rehearsal because
an authorization must bind the exact completed base report before consumption.

The second-layer rehearsal verifies:

```text
activated dry-run restart idempotency
activated local semantic-paper restart idempotency
expired authorization blocking before target artifacts
scope-mismatch blocking before local-paper artifacts
one-evaluation-to-one-orchestration consumption enforcement
```

Its immutable report binds the verified base rehearsal path and SHA-256, exact
activation evaluation and consumption identities, and resulting workflow
identities and statuses. Restart verification reopens every linked artifact.
The rehearsal is API-only and has no Alpaca, CLI, scheduler, runtime-clone,
network, or server entry point.

## Activated Dry-Run Operator Boundary

The first semantic-target operator boundary exposes only activated dry-run:

```text
schema-versioned reviewed request artifact
  -> preserve immutable request copy
  -> load exact target and activation evidence
  -> revalidate and atomically consume activation
  -> run controlled semantic-target dry-run
  -> return nonzero on any blocked stage
```

`ActivatedDryRunOperatorRequest` embeds the account snapshot, risk policy,
execution policy, reference price, evaluation time, and target identities, and
references the exact authorization, base rehearsal, passing
activation-consumption rehearsal, contributor, decision, and evaluation
artifacts. The CLI command has no mode or broker selector. Local semantic
paper, Alpaca, scheduler, runtime-clone deployment, and order submission remain
outside the operator boundary.

The read-only `inspect-activated-target` command loads the same request and
explains whether it is valid at inspection time, the current and approved
share quantities, and the intended order. It creates and consumes nothing.
This is a preview for a human operator, not an authorization or execution
claim; the execution command still performs its own durable checks.

## Bounded Autonomous Dry-Runs

The API-only autonomous dry-run runner allows repeated broker-free runs under
one immutable deployment authorization. The authorization limits the exact
symbol, contributor-set revision, strategy versions, target size, validity
window, run count, and minimum interval. Each run is atomically claimed and
durably recorded. A blocked attempt halts later attempts under that
authorization until a new authorization revision is issued.

This removes per-order human review from routine dry-runs while preserving
human approval for deployment limits and exception recovery. It is not
connected to a CLI, scheduler, runtime service, paper trading, Alpaca, or a
broker.

The separate no-network autonomous rehearsal verifies repeated allowed runs,
restart idempotency, expiry and target-limit blocking, and halt-after-block
behavior. Its immutable report reopens and checks every linked authorization,
run record, and workflow record.

The finite autonomous dry-run operator loop exposes this API through one
manually started dry-run command. Its immutable manifest binds the exact
authorization and finite ordered request list by content hash. It verifies all
inputs before starting, sleeps only between successful requests, stops on the
first block, and persists one restart-safe loop summary. It cannot discover or
generate additional requests.

The supervised autonomous dry-run service is a separate API-only controller
that can obtain one fresh request per cycle. Before every run it checks an
explicit shutdown signal and persists a health decision. Degraded or failed
health, a blocked run, provider error, maximum cycle count, or maximum runtime
stops the service. Append-only cycle events let a restart continue after the
last completed cycle without repeating it. The service has no CLI, launchd,
runtime, paper, Alpaca, broker, or scheduler connection.

Its separate no-network rehearsal verifies healthy continuation, degraded and
failed health stops, explicit shutdown, blocked-run stop, provider-error stop,
runtime-bound stop, and restart continuation. The evidence verifier rescans
the rehearsal tree for prohibited operational directories.

The production-shaped provider boundary remains API-only. A versioned provider
policy binds the exact authorization, allowed health and request source
versions, required health components, and maximum input ages. Immutable health
snapshots are converted to fail-closed cycle health checks. Immutable request
envelopes are released only when source, cycle, authorization, and freshness
all match.
