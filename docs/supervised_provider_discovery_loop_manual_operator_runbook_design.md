# Supervised Provider Discovery-To-Loop Manual Operator Runbook Design

This document designs a future manual operator runbook for one
discovery-to-loop dry-run request.

It is a design only. It does not prepare a real request, run discovery, run a
finite loop, write runtime evidence, source `.env`, use credentials, load
launchd, contact Alpaca, connect to a broker, or submit orders.

In plain language, this runbook would answer:

```text
If a human later wants to run exactly one reviewed discovery-to-loop dry-run
request, what must they check, run, archive, and stop on?
```

## Current Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit before this design bundle: `435752a`
- Runtime clone no-network command rehearsal passed at reviewed source
  `8d1398a`.

The command family under review remains:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

## Manual Run Scope

A future manual run may only process one reviewed discovery-to-loop dry-run
request. The runbook must keep the request finite and content-bound:

- one `SupervisedProviderDiscoveryLoopOperatorRequest`;
- one exact discovery-only operator request named by that request;
- one exact finite manifest produced by discovery;
- one composition output root;
- no request polling after the reviewed discovery pass;
- no recurring service;
- no scheduler;
- no launchd;
- no paper, semantic-paper, Alpaca, broker, order, or fill path.

## Required Inputs

The human operator must have a reviewed request directory containing:

```text
reviewed/supervised-provider-discovery-loop-request.json
```

That request must bind:

- discovery-only operator request path and SHA-256 hash;
- passing discovery-operator command rehearsal report path and SHA-256 hash;
- composition output root;
- creation time;
- evidence references explaining the review basis.

The request directory must not contain credentials, `.env`, broker account
snapshots, or hand-authored order files.

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

Check the reviewed request hash before running:

```bash
shasum -a 256 reviewed/supervised-provider-discovery-loop-request.json
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
- the request hash does not match the reviewed artifact;
- any required prerequisite report fails verification;
- any command would use credentials, network, broker, paper, Alpaca, orders,
  or fills.

## Planned Manual Command

If a later execution stage is explicitly approved, run only:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

The command must not be wrapped in launchd, cron, a shell loop, a background
service, or any script that discovers additional work.

## Post-Run Checks

After the command exits, capture:

- exit code;
- stdout and stderr;
- composition record path;
- discovery operator record path;
- finite manifest path, if discovery completed;
- finite loop record path, if a finite loop was reached;
- final runtime Git status;
- final runtime operational directory snapshot.

Compare the pre-run and post-run operational directory snapshots. Existing
historical directories may remain present, but the run must not create or
modify broker, Alpaca, order, fill, paper, semantic-paper, scheduler, or
launchd evidence.

## Archival Requirements

The future execution report must preserve:

- reviewed request path and SHA-256 hash;
- reviewed source commit;
- runtime source commit;
- scheduler not-loaded evidence;
- installed plist absence;
- pre-run and post-run directory snapshots;
- command line;
- exit code;
- stdout and stderr;
- all written composition/discovery/loop artifact paths and hashes;
- explicit statement that `.env` and credentials were not used.

The report should live in source documentation after review, not only in
runtime-local files.

## Pass Criteria

The future manual run passes only if:

- the command exits zero;
- discovery completes;
- exactly one finite manifest is run;
- the finite loop completes;
- restart/idempotency evidence remains consistent with prior rehearsals;
- runtime clone stays clean;
- no prohibited runtime path changes;
- no `.env`, credentials, launchd, scheduler, paper, Alpaca, broker, order, or
  fill path is used.

## Blocked Outcome Criteria

A blocked run can still be a valid safety outcome if:

- the command exits nonzero;
- the composition record explains the block;
- no later stage runs after the block;
- runtime clone stays clean;
- no prohibited path changes.

The execution report must clearly label this as blocked, not passed.

## Explicit Non-Authorization

Approving this runbook design does not authorize executing the manual run.

Even an approved manual run would not authorize:

- recurring scheduling;
- launchd;
- runtime deployment;
- semantic local paper;
- Alpaca semantic targets;
- broker access;
- orders;
- fills;
- automatic drift repair.
