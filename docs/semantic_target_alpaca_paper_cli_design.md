# Semantic-Target Alpaca Paper CLI Design

Date: 2026-06-26

Status: In review

## Purpose

This document designs the first real Alpaca paper command for semantic-target
testing. It is a software-infrastructure step, not strategy research. The goal
is to give an operator one reviewed command that can submit exactly one
semantic-target request to an Alpaca paper account and then preserve enough
evidence to explain what happened.

This design does not authorize implementation, runtime deployment, recurring
scheduling, non-paper Alpaca calls, or real-money trading by itself.

## Proposed Command

```bash
quant semantic-target alpaca-paper \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json \
  --from-env
```

The command name is intentionally specific:

- `semantic-target` means the input is already a desired signed target, not a
  legacy buy/sell/hold signal.
- `alpaca-paper` means the only broker-connected destination is Alpaca paper.
- `--request-path` means one reviewed request file drives the run.
- `--from-env` means credentials and account configuration come from the
  process environment, not the request file.

No mode selector is exposed. The command cannot choose local paper, dry-run,
real Alpaca, a scheduler, or a runtime service.

## Request Contract

The command consumes one schema-versioned
`SemanticTargetAlpacaPaperOperatorRequest`.

The request must include:

- a unique request ID;
- the expected source account and paper-only destination;
- the exact strategy, evaluation, contributor, portfolio, and risk target
  artifact paths and hashes;
- the execution root where evidence will be written;
- `alpaca_submission_enabled=True`;
- an expiry time;
- the expected symbol and whole-share target quantity;
- a human-readable reason for the test.

The command preserves a copy of the request before doing any broker-connected
work. If the preserved request already exists and differs by content, the
command fails closed.

## Preflight Gates

Before constructing an Alpaca client, the command must verify:

1. The request schema version is supported.
2. The current time is inside the request validity window.
3. The destination is explicitly Alpaca paper.
4. `alpaca_submission_enabled=True`.
5. Every linked artifact exists and matches its recorded hash.
6. The linked risk target is approved and unsatisfied.
7. The target quantity is whole-share compatible.
8. The execution root is request-scoped and not a shared generic directory.
9. No local execution plan already exists for a different request with the same
   risk-target identity.

Only after these local checks pass may the command initialize the Alpaca paper
broker adapter.

## Allowed Alpaca Paper API Use

The command may use only the paper-trading API calls needed for one request:

- paper account capability checks;
- paper asset tradability checks for the requested symbol;
- paper position lookup for the requested symbol;
- paper open-order lookup for the requested symbol;
- paper order lookup by deterministic client order ID;
- paper order submission for the approved target delta;
- paper order status and fill recovery;
- paper reconciliation needed to decide whether the target is satisfied.

The command must not use Alpaca for market-data research, strategy discovery,
portfolio scanning beyond the required reconciliation surface, non-paper
endpoints, or real-money trading.

## Execution Rules

The command delegates to the existing semantic-target Alpaca paper execution
path after preflight. That path already uses:

- deterministic execution-plan identity derived from the risk target;
- atomic plan creation;
- working-order blocking;
- deterministic client order IDs;
- broker lookup for restart recovery;
- append-only execution lifecycle events;
- reconciliation-confirmed satisfaction.

For whole-share v1, the run is satisfied only when:

```text
broker paper position equals the approved target
AND no unsettled relevant paper orders exist
AND reconciliation has no unexplained differences
```

A fill alone is not enough.

## Restart And Recovery

If the command is run again for the same request, it must reuse existing
durable evidence instead of submitting a duplicate order.

Broker lookup by deterministic client order ID is the primary recovery tool:

- order found: recover the submitted state and continue reconciliation;
- lookup unavailable: write a blocked or ambiguous event;
- conflicting order found: write a blocked or ambiguous event;
- broker reports not found: do not automatically resubmit unless the execution
  policy explicitly allows that outcome for this request.

The first implementation should keep the conservative policy: an uncertain
submission state blocks rather than resubmits.

## Evidence

The command writes evidence under the request-scoped output root:

```text
requests/
plans/
events/
recovery-evidence/
reconciliations/
drift-observations/
run-summary/
```

The final summary should include:

- request ID and request hash;
- risk target ID;
- execution plan ID;
- broker client order ID;
- order status;
- fill quantity, if any;
- final paper position for the target symbol;
- reconciliation status;
- satisfied or blocked outcome;
- all linked evidence paths and hashes.

No secrets may be written to evidence.

## Runtime Clone Boundary

A later runtime run may write bounded evidence under a reviewed runtime
`data/semantic-target/alpaca-paper/...` root. It must not modify source files,
load launchd, install a scheduler, edit credentials, or clean unrelated
runtime evidence.

Runtime-clone changes must be reversible and evidence-based. Before and after
the run, the operator should record:

- runtime git status;
- scheduler unloaded state;
- request path and hash;
- execution root;
- output evidence digest.

## Review Gate

Before implementation, review this design against:

- the fake-client rehearsal evidence;
- the fake CLI boundary evidence;
- the manual runtime runbook design;
- current Alpaca paper adapter behavior;
- the trading-safety document.

The next implementation stage should add the CLI command and tests using a
fake Alpaca paper client first. A real paper run should be a separate reviewed
manual stage after source tests pass.

## Explicit Exclusions

This design does not add or authorize:

- recurring scheduler or launchd integration;
- autonomous repeated paper trading;
- strategy research or market-data fetching through Alpaca;
- local-paper or dry-run mode selection;
- real-money trading;
- automatic drift repair;
- broad account rebalancing;
- opening a pull request.
