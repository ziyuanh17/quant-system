# Semantic-Target Alpaca Paper Evidence Verifier Design

Date: 2026-06-27

Status: In review

## Purpose

This document designs the verifier needed after the first one-request Alpaca
paper API test. The verifier should read local artifacts and decide whether
the manual paper run satisfied the reviewed request criteria.

The verifier is broker-free. It must not contact Alpaca, submit orders, source
credentials, load launchd, run a scheduler, or repair drift.

## Proposed Command

```bash
quant semantic-target verify-alpaca-paper-run \
  --request-path <prepared-alpaca-paper-request.json>
```

The request points to its paper output root. The verifier reads only local
files under that root and the request-bound target artifact paths.

## Inputs

The verifier consumes:

- `SemanticTargetAlpacaPaperOperatorRequest`;
- contributor, strategy target, portfolio target, and risk target artifacts
  referenced by the request;
- execution plan under `<output_root>/lifecycle/plans`;
- lifecycle events under `<output_root>/lifecycle/events`;
- order records under `<output_root>/orders`;
- fill records under `<output_root>/fills`;
- account snapshots under `<output_root>/snapshots`;
- reconciliation reports under `<output_root>/reconciliations`.

It should verify all request-bound hashes before reading execution evidence.

## Pass Criteria

The verifier may pass only if:

- the request schema and all request-bound hashes verify;
- the request is for `alpaca-paper`;
- `alpaca_submission_enabled=True`;
- the risk target is approved;
- the approved target is whole-share;
- the approved target is within reviewed quantity and notional bounds;
- exactly one execution plan exists for the risk target revision;
- lifecycle events are append-only and load successfully;
- final lifecycle status is `satisfied`;
- no lifecycle event is `ambiguous`, `blocked`, `rejected`, or `cancelled`;
- if the approved delta was nonzero, exactly one submitted order is linked to
  the execution plan;
- if fills exist, every fill is linked to the reviewed execution/order;
- at least one reconciliation report exists for the execution plan;
- the final reconciliation passed;
- the final paper position equals the approved target;
- no unsettled relevant orders remain in the reconciliation evidence;
- all evidence paths are inside the request output root or explicitly
  request-bound inputs.

A zero-delta request may pass with no order and no fill only if reconciliation
confirms the broker paper position already equals the approved target.

## Blocked Or Failed Outcomes

The verifier must fail, not pass, when:

- request-bound hashes fail;
- request expiry or status is invalid for the run window;
- more than one execution plan exists for the risk target;
- duplicate paper orders are present;
- an ambiguous event is present;
- reconciliation is missing or failed;
- final position does not match the approved target;
- any evidence path escapes the reviewed output root;
- order, fill, or reconciliation records are not parseable;
- a submitted order is present for a different symbol or quantity.

## Output

The command should print:

- request ID;
- risk target ID and revision;
- execution plan ID;
- final lifecycle status;
- order count;
- fill count;
- reconciliation count;
- final position;
- pass/fail result;
- block reasons.

It should exit nonzero for any failed criterion.

## Tests

Source tests should build local fake-client evidence and verify:

- a satisfied one-order, one-fill run passes;
- duplicate order evidence fails;
- missing reconciliation fails;
- ambiguous lifecycle event fails;
- wrong final position fails;
- tampered request-bound target hash fails;
- zero-delta satisfied reconciliation can pass;
- help text is broker-free.

The first implementation may use fake-client Alpaca paper rehearsal artifacts.
The verifier should not require real Alpaca evidence to be testable.

## Next Gate

After implementation and fake-evidence tests, rehearse the verifier from the
runtime clone against fake or `/tmp` evidence. Once the first real paper run
occurs, use the verifier before any broader paper workflow, scheduler, or
automation discussion.
