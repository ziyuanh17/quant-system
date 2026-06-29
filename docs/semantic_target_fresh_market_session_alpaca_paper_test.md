# Semantic-Target Fresh Market-Session Alpaca Paper Test

This document defines the next broker-connected test boundary for the
semantic-target infrastructure.

The test is manual, one-request only, and Alpaca paper only. It exists to prove
that the source-side gates can carry one reviewed semantic target through the
paper broker API and back into durable local evidence.

It does not authorize launchd, recurring scheduling, request discovery,
automatic drift repair, non-paper Alpaca behavior, real-money trading, or
strategy research.

## Why This Test Is Next

The source now has these gates in place:

- one reviewed Alpaca paper request model;
- broker-free request inspection;
- regular-session guard before broker construction;
- immutable readiness preflight report;
- readiness freshness check before broker construction;
- one-request Alpaca paper command;
- post-run broker-free evidence verification;
- optional immutable post-run verification report.

The remaining infrastructure question is no longer whether the source can
describe the intended safety boundary. The next question is whether the full
manual paper path works against the paper broker once, during a regular market
session, while producing evidence that can be independently reviewed later.

## Required Timing

Run only during a regular US equity session.

Do not run before market open, after market close, on a weekend, or on a market
holiday. The command submits a market order when the reviewed delta is nonzero;
outside the regular session, that order may queue and later fill outside the
observed test window.

## Required Inputs

Use exactly one prepared `SemanticTargetAlpacaPaperOperatorRequest`.

The request must be:

- newly prepared or freshly inspected;
- unexpired;
- whole-share only;
- symbol-scoped;
- bounded by reviewed maximum quantity and notional;
- `alpaca_submission_enabled=true`;
- tied to a request-scoped output root;
- backed by hash-bound contributor, target, portfolio, and risk artifacts.

Use a tiny target. The intended first request remains `AAPL` with a reviewed
small whole-share target unless a fresh review explicitly chooses another
symbol.

## Required Broker Scope

Allowed Alpaca paper API use:

- read paper account and position state needed for the target delta;
- read relevant paper working orders to block duplicates;
- read the requested symbol asset state;
- submit at most one paper market order if all gates pass;
- recover by deterministic client order ID;
- refresh the submitted order and fills;
- reconcile local evidence against paper broker state.

Forbidden Alpaca API use:

- non-paper endpoint use;
- real-money trading;
- market-data research through Alpaca;
- unrelated account management;
- broad portfolio scanning beyond reconciliation needs;
- more than one reviewed request.

## Procedure

From the runtime clone:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
```

Confirm the source commit is the reviewed branch commit containing:

- `quant semantic-target preflight-alpaca-paper-test`;
- `quant semantic-target alpaca-paper`;
- `--readiness-report-path`;
- `--max-readiness-age-seconds`;
- `--verification-report-path`.

Confirm the recurring Alpaca paper job is not loaded:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Confirm credential presence without printing values:

```text
QUANT_ALPACA_PAPER_API_KEY present
QUANT_ALPACA_PAPER_SECRET_KEY present
QUANT_ALPACA_PAPER_ACCOUNT_ID present
QUANT_ALPACA_PAPER_URL_OVERRIDE absent or paper endpoint only
```

Create fresh readiness evidence:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target preflight-alpaca-paper-test \
  --request-path <reviewed-request-path> \
  --report-path <fresh-readiness-report-path> \
  --planned-verification-report-path <planned-verification-report-path>
```

Stop if the readiness command exits nonzero.

Run exactly one paper command:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path <reviewed-request-path> \
  --from-env \
  --readiness-report-path <fresh-readiness-report-path> \
  --max-readiness-age-seconds 900 \
  --verification-report-path <planned-verification-report-path>
```

Stop after this one request. Do not run a loop, scheduler, discovery command,
or legacy signal refresh workflow.

## Evidence To Preserve

Preserve:

- runtime source commit and status;
- local clock and market-session evidence;
- request path and SHA-256;
- readiness report path and SHA-256;
- verification report path and SHA-256;
- output root listing;
- execution plan;
- execution events;
- order record;
- fill record;
- account snapshots;
- reconciliation report;
- command stdout and exit code.

After the run, verify the saved report without broker access:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target verify-alpaca-paper-report \
  --report-path <planned-verification-report-path>
```

## Stop Conditions

Stop before broker construction if:

- runtime source is not the reviewed source;
- runtime has unrelated tracked changes;
- launchd or the recurring scheduler is loaded;
- the request is expired;
- request hashes fail;
- the readiness report fails, is stale, mismatched, or has issues;
- the planned verification report path already exists;
- the regular market session is closed.

Stop after broker interaction if:

- the command writes a durable blocked state;
- working orders exist;
- reconciliation is not passing;
- the post-run verifier fails;
- the saved verification report cannot be independently verified.

## Expected Outcome

Acceptable outcomes:

- satisfied target with exactly one reviewed paper order and passing
  reconciliation; or
- durable blocked state with no duplicate paper order.

Unacceptable outcomes:

- duplicate paper order submission;
- queued market order outside the regular session;
- missing post-run verification report;
- satisfaction without passing reconciliation;
- any non-paper Alpaca or real-money behavior.
