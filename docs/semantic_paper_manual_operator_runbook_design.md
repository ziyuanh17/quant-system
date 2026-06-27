# Semantic-Paper Manual Operator Runbook Design

This document designs a future manual operator runbook for one reviewed
semantic-paper local-paper request from the runtime clone.

It is a design only. It does not prepare a request, inspect a request, run
local semantic paper, write runtime evidence, source `.env`, use credentials,
load launchd, contact Alpaca, connect to a broker, or submit orders.

In plain language, this runbook would answer:

```text
If a human later wants to run exactly one reviewed local-data semantic-paper
request from the runtime clone, what must they check, run, archive, and stop on?
```

## Current Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Runtime clone no-network synthetic command rehearsal passed at reviewed
  source `2614ebc`.

The command family under review is:

```bash
quant semantic-paper prepare-momentum-request
quant semantic-paper inspect-activated-target
quant semantic-paper activated-target
```

## Manual Run Scope

A future manual run may only process one reviewed local-data semantic-paper
request. The runbook must keep the run finite and content-bound:

- one reviewed market-bar input file;
- one symbol;
- one reviewed request ID;
- one generated request bundle;
- one read-only inspection;
- one local semantic-paper output root;
- at most two `activated-target` invocations against the same request, where
  the second invocation is only an idempotency/restart check;
- no request polling;
- no recurring service;
- no scheduler;
- no launchd;
- no Alpaca semantic target;
- no broker-network order path.

Unlike the prior `/tmp` synthetic runtime rehearsal, this future manual run may
write local semantic-paper evidence under a reviewed runtime output root. That
is the capability being designed and must be separately approved before
execution.

## Required Inputs

The human operator must identify:

```text
reviewed source commit
runtime clone path
reviewed market-bar CSV path
symbol
quantity for buy signal
fast and slow windows
initial local-paper cash
initial local-paper position
request ID
request output root
activation output root
local-paper output root
```

Recommended reviewed runtime paths for the first manual run:

```text
data/normalized/market_bars/AAPL.csv
data/semantic-target/manual-local-paper/requests/<request-id>
data/semantic-target/manual-local-paper/activation/<request-id>
data/semantic-target/manual-local-paper/output/<request-id>
```

The reviewed market-bar input must be local data only. It must not require a
fresh network fetch, broker account snapshot, `.env`, credentials, or Alpaca
API call.

## Pre-Run Checks

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

Check the reviewed market-bar input:

```bash
test -f data/normalized/market_bars/AAPL.csv
shasum -a 256 data/normalized/market_bars/AAPL.csv
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

Stop before running if:

- the runtime clone is dirty;
- the runtime clone is not at the reviewed commit;
- the Alpaca paper launchd job is loaded;
- the installed launchd plist exists;
- `.env` would need to be sourced;
- the market-bar input hash does not match the reviewed artifact;
- output roots already contain an unrelated request;
- any command would use credentials, network, broker, Alpaca, or
  broker-network orders.

## Planned Manual Commands

If a later execution stage is explicitly approved, first prepare exactly one
request:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
request_id=reviewed-aapl-momentum-local-paper-YYYYMMDD

PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request \
  --request-id "$request_id" \
  --data data/normalized/market_bars/AAPL.csv \
  --symbol AAPL \
  --quantity 2 \
  --fast-window 5 \
  --slow-window 20 \
  --min-rows 20 \
  --initial-cash 100000 \
  --output-root "data/semantic-target/manual-local-paper/requests/$request_id"
```

Then inspect the generated request:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target \
  --request-path "data/semantic-target/manual-local-paper/requests/$request_id/inputs/requests/$request_id.json"
```

If inspection reports the expected reviewed intent, run local semantic paper:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path "data/semantic-target/manual-local-paper/requests/$request_id/inputs/requests/$request_id.json" \
  --activation-root "data/semantic-target/manual-local-paper/activation/$request_id" \
  --output-root "data/semantic-target/manual-local-paper/output/$request_id"
```

Run the same command a second time only as a restart/idempotency check:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target \
  --request-path "data/semantic-target/manual-local-paper/requests/$request_id/inputs/requests/$request_id.json" \
  --activation-root "data/semantic-target/manual-local-paper/activation/$request_id" \
  --output-root "data/semantic-target/manual-local-paper/output/$request_id"
```

Do not wrap these commands in launchd, cron, a shell loop, a background service,
or any script that discovers additional work.

## Post-Run Checks

After the command exits, capture:

- exit codes;
- stdout and stderr for preparation, inspection, first run, and restart check;
- generated request path and hash;
- authorization path and hash;
- strategy target path and hash;
- strategy evaluation path and hash;
- orchestration record path and hash;
- local semantic-paper state path and hash;
- order count, fill count, final positions, and cash;
- reconciliation report ID;
- final runtime Git status;
- final runtime operational directory snapshot.

Compare the pre-run and post-run operational directory snapshots. Existing
historical directories may remain present. The first approved manual run is
expected to create the reviewed `data/semantic-target/manual-local-paper/...`
roots, but it must not create or modify broker-network order, broker-network
fill, scheduler, launchd, Alpaca, or live-account evidence.

## Archival Requirements

The future execution report must preserve:

- reviewed source commit;
- runtime source commit;
- scheduler not-loaded evidence;
- installed plist absence;
- market-bar input path and SHA-256 hash;
- pre-run and post-run directory snapshots;
- exact command lines;
- exit codes;
- stdout and stderr;
- all generated artifact paths and SHA-256 hashes;
- final local-paper state summary;
- explicit statement that `.env`, credentials, Alpaca, and broker-network
  paths were not used.

The report should live in source documentation after review, not only in
runtime-local files.

## Pass Criteria

The future manual run passes only if:

- request preparation exits zero;
- inspection exits zero and reports the reviewed intent;
- first local semantic-paper run reaches `execution_completed` and `satisfied`
  or produces a clearly blocked local-only safety result;
- restart check reuses the same orchestration and does not duplicate local
  orders or fills;
- runtime clone stays clean except for reviewed generated evidence if that
  evidence is intentionally untracked;
- no `.env`, credentials, launchd, scheduler, Alpaca, broker-network order, or
  broker-network fill path is used.

## Blocked Outcome Criteria

A blocked run can still be a valid safety outcome if:

- the command exits nonzero;
- the output evidence explains the block;
- no later stage runs after the block unless the runbook explicitly allows a
  read-only inspection;
- runtime clone has no unexpected changes;
- no prohibited path changes occur.

The execution report must clearly label this as blocked, not passed.

## Explicit Non-Authorization

Approving this runbook design does not authorize executing the manual run.

Even an approved manual run would not authorize:

- recurring scheduling;
- launchd;
- Alpaca semantic targets;
- broker access;
- broker-network orders;
- broker-network fills;
- real-money trading;
- automatic drift repair.

