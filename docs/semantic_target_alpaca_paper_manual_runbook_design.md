# Semantic-Target Alpaca Paper Manual Runbook Design

This document designs a future manual runtime runbook for one reviewed
semantic-target Alpaca paper test.

It is a design only. It does not source `.env`, use credentials, contact
Alpaca, submit paper orders, load launchd, run a scheduler, or touch real-money
trading.

In plain language, this runbook answers:

```text
If a human later wants to run exactly one reviewed semantic-target request
through Alpaca paper, what must they check, run, archive, and stop on?
```

## Current Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Runtime local semantic-paper manual run passed.
- Semantic-target Alpaca paper testing boundary is documented.
- Source-level fake-client Alpaca paper rehearsal passed.
- Library-level executor:
  `run_alpaca_semantic_target_paper`
- Required library gate:
  `alpaca_submission_enabled=True`

The next executable stage should not yet be recurring or scheduler-driven. It
should be one manually started paper test against one reviewed request.

## Manual Run Scope

A future manual run may only process one reviewed semantic-target Alpaca paper
request.

Allowed:

- one reviewed request artifact;
- one risk target revision;
- one symbol;
- one bounded maximum quantity;
- one bounded maximum notional;
- one deterministic client order ID;
- one manual command invocation;
- one optional restart/idempotency invocation of the same command;
- paper account/position reads required for the decision;
- asset tradability read for the reviewed symbol;
- order and fill reads required for restart recovery and reconciliation;
- durable runtime evidence under a reviewed output root.

Forbidden:

- launchd;
- recurring scheduling;
- request discovery;
- broad polling;
- market-data research through Alpaca;
- quote lookup through Alpaca;
- non-paper Alpaca endpoint use;
- real-money trading;
- more than one reviewed request;
- automatic drift repair.

## Required Request Contract

The future manual run should consume a checked and hash-bound request shaped
like `SemanticTargetAlpacaPaperOperatorRequest`.

The request must bind:

```text
request ID
contributor set path and hash
strategy target decision paths and hashes
portfolio target path and hash
risk target path and hash
risk policy
execution lifecycle policy
reference price
safety config
runtime output root
evaluated_at
alpaca_submission_enabled = true
allowed symbol
allowed maximum quantity
evidence references
```

The safety config must state:

```text
mode = live
broker_name = alpaca-paper
live_trading_enabled = true
live_trading_confirmation = I_UNDERSTAND_LIVE_TRADING_RISK
max_order_notional = reviewed value
```

The `live` mode here is the existing live-shaped safety gate for
broker-connected paper trading. It does not authorize real-money trading.

## Required Preflight

Before any future run, capture:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
git stash list --max-count=1
```

Check scheduler state directly:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Check the reviewed request and artifact hashes:

```bash
shasum -a 256 reviewed/semantic-target-alpaca-paper-request.json
```

Check environment scope without printing secrets:

```text
QUANT_ALPACA_PAPER_API_KEY present
QUANT_ALPACA_PAPER_SECRET_KEY present
QUANT_ALPACA_PAPER_BASE_URL is the paper endpoint
QUANT_BROKER = alpaca-paper
QUANT_MAX_ORDER_NOTIONAL matches the reviewed request
```

Take a runtime operational directory snapshot:

```bash
for path in \
  data/live/orders \
  data/live/fills \
  data/live/account_snapshots \
  data/live/reconciliation \
  data/semantic-target \
  data/workflows \
  data/scheduler \
  data/paper \
  data/web \
  logs
do
  if test -e "$path"; then
    /usr/bin/stat -f '%N %m' "$path"
  else
    printf '%s absent\n' "$path"
  fi
done
```

Stop before any Alpaca call if:

- the runtime clone has unrelated modifications;
- the Alpaca paper launchd job is loaded;
- the installed launchd plist exists;
- the base URL is not the Alpaca paper endpoint;
- the request hash does not match the reviewed artifact;
- any target artifact hash does not match the reviewed request;
- the request is expired or stale;
- the request symbol differs from the allowed symbol;
- the target quantity exceeds the allowed maximum;
- current paper working orders exist for the symbol;
- the current paper position would require an unreviewed short or reversal;
- the command would use non-paper Alpaca behavior.

## Planned Manual Command

The eventual command should be a dedicated semantic-target Alpaca paper command
or a small approved runner that does exactly one request. It should not reuse
the legacy signal-oriented `quant workflow alpaca-paper-refresh` command.

Intended shape:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
set -a
source .env
set +a

PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path reviewed/semantic-target-alpaca-paper-request.json
```

The future command must:

- load exactly one reviewed request;
- verify every bound hash before constructing the Alpaca client;
- verify the paper endpoint before constructing the Alpaca client;
- construct `AlpacaPaperBrokerClient` only after the request and safety gates
  pass;
- call `run_alpaca_semantic_target_paper` with
  `alpaca_submission_enabled=True`;
- require `--from-env` so credentials come from the operator environment, not
  from the request artifact;
- write evidence only under the reviewed output root;
- exit nonzero for blocked or ambiguous outcomes.

The future command must not:

- run in a loop;
- discover additional requests;
- install or start launchd;
- call the legacy signal-oriented paper workflow;
- submit more than the one reviewed target delta;
- call non-paper Alpaca endpoints.

## Allowed Alpaca Paper API Uses

For this one request only, the future command may use:

- submit paper market order;
- get paper account;
- get paper positions;
- get asset details for the reviewed symbol;
- get paper orders needed for working-order detection and restart lookup;
- get paper order by deterministic client order ID;
- get paper order by broker order ID for refresh;
- read fills derived from the reviewed paper order for reconciliation.

No other Alpaca API purpose is allowed in this stage.

## Post-Run Checks

After the command exits, capture:

- exit code;
- stdout and stderr;
- final status: satisfied, blocked, ambiguous, or failed;
- execution plan path and hash;
- lifecycle event paths and hashes;
- submitted paper order ID, if any;
- deterministic client order ID, if any;
- fill IDs and quantities, if any;
- reconciliation report path and hash;
- paper account snapshot paths and hashes;
- runtime Git status;
- runtime operational directory snapshot;
- explicit statement that no non-paper Alpaca behavior was used.

If a restart/idempotency check is approved, repeat the exact same command once
and verify that it does not submit a duplicate paper order.

## Pass Criteria

The manual paper test passes only if:

- every preflight gate passes;
- exactly one reviewed request is processed;
- the endpoint is verified as paper-only;
- every target artifact hash matches the reviewed request;
- the command processes only the reviewed symbol and quantity bound;
- any paper order submission is the exact required delta;
- repeated execution does not submit a duplicate paper order;
- satisfaction requires reconciliation-confirmed paper position;
- runtime evidence is durable and hashable;
- scheduler remains unloaded;
- no non-paper Alpaca API behavior is used.

## Blocked Outcome Criteria

A blocked paper test is valid safety evidence if:

- no paper order is submitted after the block;
- the output explains the block;
- evidence is durable and hashable;
- scheduler remains unloaded;
- no non-paper Alpaca behavior is used.

The execution report must label this as blocked, not passed.

## Explicit Non-Authorization

Approving this runbook design does not authorize executing an Alpaca paper
test.

Even an approved manual Alpaca paper test would not authorize:

- launchd;
- recurring scheduling;
- broad request discovery;
- market-data research through Alpaca;
- non-paper Alpaca API behavior;
- real-money trading;
- automatic drift repair;
- processing more than one reviewed request.
