# Semantic-Target Alpaca Paper Transition Exposure Design

Date: 2026-07-01

Status: In review

## Purpose

This document designs how the existing explicit target-transition lifecycle
should later be connected to Alpaca paper.

This is a design stage only. It does not enable Alpaca reversal execution,
submit paper orders, source credentials, touch the runtime clone, load launchd,
or add scheduler behavior.

In this document, "exposure boundary" means the narrow code doorway that would
be allowed to call Alpaca paper after every local check has already passed. The
point of this stage is to design that doorway before opening it.

## Current State

The semantic-target Alpaca paper command currently uses the older one-order
execution lifecycle. That path can submit ordinary same-side or flattening
targets when the reviewed request, market-session, readiness, safety, and
broker gates pass.

Cross-zero transitions remain blocked before Alpaca submission. For example,
`AAPL=-1 -> AAPL=+2` is not allowed to become one net `BUY 3` paper order.
The source blocks that case with:

```text
cross-zero reversal requires explicit close/open execution plan
```

The source now has the local pieces needed to promote this safely in a later
stage:

- durable transition plans with one or two explicit legs;
- append-only per-leg lifecycle events;
- deterministic per-leg client order IDs;
- fake-broker multi-leg transition rehearsal;
- local semantic-paper transition bridge;
- local transition CLI and read-only evidence verifier;
- runtime-clone command rehearsal proving restart reuse without Alpaca.

Those pieces are still local and broker-free for transition execution.

## Design Goal

The future Alpaca paper transition runner should map the proven local
transition lifecycle onto Alpaca paper without changing its semantics.

The pipeline should be:

```text
reviewed request
  -> readiness and freshness gates
  -> current Alpaca paper account snapshot
  -> durable execution plan
  -> durable transition plan
  -> leg 1 pre-submit revalidation
  -> leg 1 Alpaca paper submission or recovery
  -> leg 1 terminal order evidence
  -> account-wide reconciliation
  -> leg 2 pre-submit revalidation, if needed
  -> leg 2 Alpaca paper submission or recovery
  -> final account-wide reconciliation
  -> execution satisfaction or durable block
```

The close/open meaning of the transition must remain visible all the way down
to evidence. A short-to-long reversal is two lifecycle decisions, even if both
legs happen to use `BUY`.

## Required Boundary Rules

The future Alpaca paper transition boundary must be paper-only:

- require `broker_name=alpaca-paper`;
- require `TradingMode.LIVE` only inside the existing paper-safety convention;
- require `alpaca_submission_enabled=True`;
- require `--from-env` for credentials;
- reject non-paper endpoint configuration;
- keep real-money trading unimplemented;
- keep launchd and recurring scheduler out of scope;
- process exactly one reviewed request per command run.

The command must not expose a generic broker selector, mode selector,
strategy-discovery selector, runtime selector, loop option, or scheduler
option.

## Leg Submission Rules

Each transition leg must be handled independently:

- use the deterministic leg client order ID;
- write an append-only event before broker interaction stating the intended
  leg and required starting position;
- revalidate the current broker position immediately before submission;
- block if any relevant working order exists;
- block if the strategy target, portfolio target, risk target, request,
  readiness report, or safety configuration is stale or mismatched;
- apply risk checks to both the order and the resulting position after the
  leg;
- submit only the current leg, never the whole net transition as one order.

For a two-leg reversal, leg 2 must not submit until leg 1 is terminal and
reconciliation confirms the required intermediate position. For `-1 -> +2`,
that means the short-cover leg must reconcile the position to `0` before the
long-opening leg may submit.

## Restart And Recovery

Restart recovery must be based on Alpaca lookup by deterministic client order
ID for each leg. The wrapper already exposes `orders_by_client_order_id(...)`
using Alpaca's `get_order_by_client_id(...)`; the transition runner must use it
per leg.

Recovery outcomes should be explicit:

```text
broker order found       -> recover submitted or terminal state
broker proves not found  -> block for reviewed recovery policy
lookup unavailable       -> ambiguous and blocked
conflicting orders found -> ambiguous and blocked
```

The command must not automatically resubmit only because lookup returns "not
found". Broker visibility can lag, and a duplicate paper order would be worse
than a blocked run.

## Satisfaction Rule

A filled order alone is not enough. For Alpaca paper transition V1, satisfaction
requires:

```text
all transition legs are terminal and reconciled
AND broker position equals the approved target
AND no relevant working orders exist
AND account-wide reconciliation passes without unexplained differences
```

If reconciliation fails, is unavailable, or reports unexplained differences,
the execution remains unsatisfied or blocked. Later divergence is drift and
should remain detect-only.

## Evidence Requirements

The future runner must write request-scoped evidence:

- reviewed request hash;
- readiness report hash and freshness decision;
- Alpaca paper account snapshot before planning;
- durable execution plan;
- durable transition plan;
- per-leg lifecycle events;
- per-leg client order ID;
- per-leg broker lookup evidence;
- per-leg order and fill evidence;
- per-leg reconciliation report;
- final account-wide reconciliation report;
- final status and block reason, if blocked.

The verifier should be extended before any real Alpaca transition test. It must
read evidence only and prove that the command did not skip the close/open
boundary, did not submit leg 2 before leg 1 reconciled, and did not duplicate
orders across a restart.

## Fail-Closed Conditions

The future Alpaca paper transition command should exit nonzero without
submitting a new order when any of these conditions occur:

- request expired or hash-mismatched;
- readiness report missing, stale, or for a different request;
- regular US equity session closed;
- endpoint is not Alpaca paper;
- current broker position differs from the required leg start;
- any relevant working order exists;
- target quantity is fractional or violates broker precision;
- quantity or notional exceeds reviewed limits;
- asset is not tradable;
- short exposure is not allowed or not borrowable when required;
- broker lookup is unavailable or ambiguous;
- reconciliation has unexplained differences;
- launchd or a recurring semantic-target scheduler is unexpectedly active for
  this path.

Blocked evidence is a valid outcome. Silent retry is not.

## Recommended Next Stage

Do not connect this directly to real Alpaca paper yet.

The next implementation stage should add a broker-free, fake-client Alpaca
paper transition adapter rehearsal:

1. reuse the existing Alpaca paper client interface and fake trading client;
2. run the durable transition plan through per-leg Alpaca-shaped calls;
3. prove restart recovery by client order ID per leg;
4. prove leg 2 is blocked until leg 1 reconciles;
5. prove ambiguous lookup blocks without resubmission;
6. extend the read-only verifier for Alpaca-shaped transition evidence;
7. keep the real `quant semantic-target alpaca-paper` cross-zero guard in
   place.

Only after that source-level rehearsal is reviewed should a later stage
consider a one-request, market-session Alpaca paper transition test.
