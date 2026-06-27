# Semantic-Target Alpaca Paper Testing Boundary

This document designs the next promotion boundary for semantic-target Alpaca
paper testing.

It is a design only. It does not source `.env`, use credentials, contact
Alpaca, submit paper orders, load launchd, run a scheduler, or touch real-money
trading.

In plain language, this boundary answers:

```text
What exactly may a future semantic-target Alpaca paper test do, and what must
remain forbidden while we move from local semantic paper toward broker-backed
paper testing?
```

## Current Reviewed State

- Local semantic-paper source command exists:
  `quant semantic-paper activated-target`.
- Runtime clone import/help rehearsal passed.
- Runtime clone synthetic no-network command rehearsal passed.
- Runtime clone manual local-data semantic-paper run passed.
- Library-level Alpaca paper semantic-target execution exists through
  `run_alpaca_semantic_target_paper`.
- Source tests cover activation gating, satisfaction, notional blocking,
  short blocking, ambiguous submission recovery, reconciliation failure,
  untradable assets, and operational-risk unavailability.

The existing library-level gate is:

```text
alpaca_submission_enabled=True
```

That gate is required in addition to live-shaped paper safety checks.

## Allowed Alpaca Paper Scope

A future execution stage may use Alpaca only for paper-trade testing. The
allowed API purpose is limited to:

- submit one semantic-target paper order when all gates pass;
- read paper account/position state needed for that order decision;
- read paper asset tradability details needed for risk checks;
- read paper order/fill state needed for reconciliation and restart recovery;
- write local evidence for the paper test.

The future stage must not use Alpaca for:

- real-money trading;
- market data research;
- quote lookup;
- recommendations;
- account management outside the paper order/reconciliation path;
- broad portfolio discovery unrelated to the reviewed request;
- recurring polling outside the bounded test;
- any non-paper endpoint or non-paper account.

## Required Inputs For A Future Paper Test

The future stage must be driven by one reviewed semantic-target request bundle,
not by an open-ended strategy scan.

Required reviewed inputs:

```text
reviewed source commit
runtime clone commit
request ID
strategy target decision path and hash
strategy evaluation path and hash
contributor set path and hash
portfolio target path and hash
risk target path and hash
reference price and evidence source
paper output root
max order notional
allowed symbol
allowed side
allowed maximum quantity
expiration time
```

The reviewed request must declare:

```text
broker = alpaca-paper
alpaca_submission_enabled = true
trading_mode = live
broker_name = alpaca-paper
live_trading_enabled = true
live_trading_confirmation = I_UNDERSTAND_LIVE_TRADING_RISK
```

The use of `trading_mode = live` here reflects the existing live-shaped safety
gate for broker-connected paper trading. It does not mean real-money trading is
implemented or authorized.

## Preflight Checks

Before any future Alpaca paper test, capture:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
```

Check scheduler state directly:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Check environment scope without printing secrets:

```text
QUANT_ALPACA_PAPER_API_KEY present
QUANT_ALPACA_PAPER_SECRET_KEY present
QUANT_ALPACA_PAPER_BASE_URL is paper endpoint
QUANT_BROKER is alpaca-paper
QUANT_MAX_ORDER_NOTIONAL is reviewed value
```

Take a runtime operational directory snapshot:

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

Stop before any Alpaca call if:

- the runtime clone has unrelated changes;
- the scheduler is loaded;
- the installed launchd plist exists;
- the base URL is not the Alpaca paper endpoint;
- the request is expired or stale;
- the request symbol, side, or quantity exceeds the reviewed bounds;
- the paper account already has working orders for the symbol;
- current paper position would require an unreviewed reversal or short;
- the required reviewed artifacts or hashes do not match;
- any command would use non-paper Alpaca behavior.

## Required Execution Semantics

The future paper test must preserve the semantic-target lifecycle:

```text
strategy target
-> portfolio target
-> risk target
-> Alpaca paper execution lifecycle
-> paper broker state
-> reconciliation-confirmed satisfaction
```

The execution must:

- derive order intent from the approved risk target;
- account for current paper position;
- fail closed on working paper orders;
- use deterministic client order ID for restart lookup;
- treat lookup unavailable as ambiguous and blocked;
- treat conflicting paper orders as ambiguous and blocked;
- mark a target satisfied only after reconciliation confirms the paper broker
  position and there are no relevant unsettled orders;
- keep drift policy detect-only.

## Evidence To Capture

The future execution report must preserve:

- reviewed request path and hash;
- reviewed source commit and runtime commit;
- scheduler not-loaded evidence;
- installed plist absence;
- paper endpoint verification without secrets;
- request validity evaluation;
- risk target ID and revision;
- deterministic client order ID;
- submitted order ID, if any;
- terminal order status;
- fill IDs and quantities, if any;
- paper account snapshot before and after;
- reconciliation report path and hash;
- lifecycle event paths and hashes;
- final status: satisfied, blocked, ambiguous, or failed;
- explicit statement that no non-paper Alpaca API behavior was used.

## Pass Criteria

The first paper test passes only if:

- every reviewed preflight gate passes;
- exactly one reviewed risk target is processed;
- Alpaca endpoint is paper-only;
- paper API use is limited to order, position/account, asset, order status,
  fill, and reconciliation needs for this one request;
- order submission occurs only if the approved delta is nonzero;
- repeated execution does not submit a duplicate paper order;
- satisfaction requires reconciliation, not just a fill;
- runtime evidence is durable and hashable;
- scheduler remains unloaded;
- no real-money, non-paper, market-data, research, or account-management API
  behavior is used.

## Blocked Outcome Criteria

A blocked paper test can still be a valid safety result if:

- the output explains the block;
- no order is submitted after the block;
- runtime evidence is durable;
- scheduler remains unloaded;
- no non-paper Alpaca behavior is used.

The execution report must label this as blocked, not passed.

## Explicit Non-Authorization

Approving this boundary does not authorize executing an Alpaca paper test.

Even an approved paper test would not authorize:

- recurring scheduling;
- launchd;
- broad polling;
- market-data research through Alpaca;
- non-paper Alpaca API behavior;
- real-money trading;
- automatic drift repair;
- more than one reviewed request.

