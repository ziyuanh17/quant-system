# Semantic-Target Alpaca Paper Manual Test Design

Date: 2026-06-26

Status: In review

## Purpose

This document designs the first real Alpaca paper API test for semantic
targets. It is the first stage that may contact Alpaca paper and may submit one
paper order, but only after fresh preflight evidence passes.

The design is intentionally manual and one-request only. It does not authorize
launchd, recurring scheduling, request discovery, autonomous repeated paper
trading, non-paper Alpaca behavior, real-money trading, automatic drift repair,
or strategy research.

## Required Starting Point

Before the paper API test, the following source stages must be reviewed:

- semantic-target Alpaca paper testing boundary;
- fake-client Alpaca paper rehearsal;
- fake-client CLI boundary;
- source Alpaca paper CLI;
- runtime command visibility rehearsal;
- broker-free request preparer;
- runtime request-preparation rehearsal.

The runtime clone must contain the reviewed source commit that includes
`quant semantic-target alpaca-paper` and
`quant semantic-target prepare-alpaca-paper-request`.

## Test Request

The first manual test should use one reviewed request prepared by:

```bash
quant semantic-target prepare-alpaca-paper-request
```

The request must be small and explicit:

```text
symbol: AAPL
unit: shares
approved target: whole-share quantity
allowed maximum quantity: reviewed value
max order notional: reviewed value
valid_until: near-term expiry
alpaca_submission_enabled: true
broker: alpaca-paper
```

The request file must be hashed immediately before execution:

```bash
shasum -a 256 <request-path>
```

If the request has expired, was edited, or its target artifacts no longer match
the request hashes, stop before sourcing credentials.

The first paper test should run only during a regular US equity session. A
market order submitted outside the session may remain queued and later fill
outside the observed rehearsal window, creating exactly the working-order
ambiguity this stage is meant to avoid.

## Fresh Preflight

Capture the following immediately before any Alpaca API interaction:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
```

Scheduler and launchd:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Environment presence without printing values:

```text
QUANT_ALPACA_PAPER_API_KEY present
QUANT_ALPACA_PAPER_SECRET_KEY present
QUANT_ALPACA_PAPER_ACCOUNT_ID present
QUANT_ALPACA_PAPER_URL_OVERRIDE absent or paper endpoint only
```

Runtime directory snapshot:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/semantic-target
data/workflows
data/scheduler
data/paper
data/web
logs
```

Stop before sourcing credentials if:

- runtime source is not the reviewed commit;
- runtime has unrelated tracked changes;
- scheduler is loaded;
- launchd plist exists;
- request hash differs from the reviewed value;
- request is expired;
- request target artifacts fail hash validation;
- target is fractional;
- target exceeds the reviewed quantity or notional bound;
- the command path is not the reviewed semantic-target Alpaca paper command.
- the regular US equity session is closed for a market-order test.

## Command

Only after preflight passes, source environment variables and run exactly one
request:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
set -a
source .env
set +a

PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path <reviewed-request-path> \
  --from-env
```

The command must not be wrapped in a loop. Do not run legacy
`quant workflow alpaca-paper-refresh`. Do not run request discovery. Do not run
the recurring scheduler.

## Allowed Alpaca Paper API Use

Allowed only for this one request:

- paper account and position lookup needed for the target delta;
- paper open-order lookup needed for working-order blocking;
- paper asset tradability lookup for the requested symbol;
- paper order lookup by deterministic client order ID for restart recovery;
- one paper market order submission if the reviewed delta is nonzero and all
  gates pass;
- paper order/fill refresh needed for terminal status;
- paper reconciliation needed to decide satisfaction.

Forbidden:

- non-paper endpoint use;
- real-money trading;
- market-data research through Alpaca;
- quote lookup through Alpaca;
- broad portfolio scanning unrelated to reconciliation;
- account management outside order/reconciliation needs;
- automatic drift repair;
- more than one reviewed request.

## Restart Check

If the first run exits after submitting or satisfying the request, run the same
command once more only if the evidence indicates restart/idempotency checking
is safe.

The second run must:

- reuse the same execution plan;
- recover or refresh the same deterministic client order ID;
- not submit a duplicate paper order;
- preserve reconciliation-confirmed satisfaction or a durable blocked state.

If the first run is ambiguous, do not rerun automatically. Inspect broker and
local evidence first.

## Pass Criteria

The manual paper API test passes only if:

- every preflight gate is recorded and passes;
- exactly one reviewed request is processed;
- Alpaca endpoint is paper-only;
- no scheduler or launchd service is present;
- request and target artifact hashes match;
- any submitted paper order matches the approved target delta;
- no duplicate paper order is submitted on an approved restart check;
- final satisfaction requires reconciliation, not only a fill;
- all evidence is durable and request-scoped;
- no non-paper Alpaca behavior occurs.

## Blocked Or Failed Outcomes

A blocked outcome is acceptable safety evidence if:

- no paper order is submitted after the block;
- the reason is clear in local evidence;
- scheduler remains absent;
- no non-paper Alpaca behavior occurs.

An ambiguous submission outcome is not a pass. It requires separate recovery
review before any repeat command.

## Evidence Document

The actual paper test must produce a separate evidence document with:

- source and runtime commits;
- runtime status before and after;
- scheduler and plist evidence;
- request path and hash;
- environment presence summary without secrets;
- command stdout/stderr and exit code;
- generated plan/event/order/fill/snapshot/reconciliation paths;
- final status;
- duplicate-order check result, if run;
- explicit statement of whether a paper order was submitted;
- explicit statement that no non-paper Alpaca API behavior was used.

## Next Gate

If this one-request manual paper API test passes, the next infrastructure stage
should not jump to automation. The next stage should first add a reviewed
manual paper evidence verifier that reads the generated artifacts and checks
the pass criteria mechanically.
