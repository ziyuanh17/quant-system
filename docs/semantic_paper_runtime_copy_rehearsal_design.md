# Semantic-Paper Runtime Copy Rehearsal Design

This document designs the next runtime-clone rehearsal for the reviewed
semantic-paper request and local-paper command family.

It is a design only. It does not copy source to the runtime clone, run request
generation, run local semantic paper, load launchd, use credentials, contact
Alpaca, connect to a broker, or submit orders.

In plain language, this rehearsal would answer one narrow question:

```text
Can the reviewed semantic-paper source be placed in the runtime clone and
imported there without accidentally starting any operational behavior?
```

## Current Reviewed Source

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Command family under review:

```bash
quant semantic-paper prepare-momentum-request --help
quant semantic-paper inspect-activated-target --help
quant semantic-paper activated-target --help
```

These are help checks only. Showing CLI help parses command metadata and exits
before loading a request, generating artifacts, consuming activation, running
local paper, or touching broker-connected code.

## Scope

The rehearsal may only:

1. verify the development workspace is clean at the reviewed source;
2. verify the recurring Alpaca paper launchd job is not loaded;
3. verify the installed Alpaca paper launchd plist is absent;
4. inspect the runtime clone Git status and current commit;
5. fast-forward the runtime clone to one reviewed source commit, if separately
   approved for the execution stage;
6. verify the runtime clone imports the package with bytecode writing disabled;
7. verify the runtime clone exposes CLI help for the reviewed semantic-paper
   commands;
8. verify no operational directories or Git working-tree changes were created
   by the import/help checks.

The rehearsal must not:

- run `quant semantic-paper prepare-momentum-request` without `--help`;
- run `quant semantic-paper inspect-activated-target` without `--help`;
- run `quant semantic-paper activated-target` without `--help`;
- create or inspect request files;
- create target, activation, lifecycle, reconciliation, order, or fill
  artifacts;
- load, unload, or kickstart launchd;
- source `.env`;
- read broker credentials;
- contact Alpaca;
- run a scheduler;
- submit or rehearse broker-network orders.

## Planned Execution Commands

The execution stage should start in the development workspace:

```bash
cd /Users/mochifufu/Code/quant-system
git status --short --branch
git rev-parse --short HEAD
```

Check the scheduler directly:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Inspect the runtime clone before any update:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
```

If and only if the execution stage is separately approved, update by
fast-forwarding to the reviewed source:

```bash
git fetch origin main
git merge --ff-only <reviewed-source-commit>
```

Then verify imports and help only, with bytecode writing disabled:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import quant; print('quant_import_ok')"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper prepare-momentum-request --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper inspect-activated-target --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-paper activated-target --help
```

The help commands are allowed because they do not load market data, request
paths, activation artifacts, broker credentials, or runtime data.

## Evidence To Capture

The execution report should record:

- development workspace branch, commit, and clean status;
- runtime clone branch, commit before update, and commit after update;
- scheduler not-loaded evidence;
- installed launchd plist absence;
- import command exit code and output;
- semantic-paper help command exit codes and output;
- list of operational directories checked before and after;
- runtime clone Git status after import/help;
- confirmation that no new `__pycache__` directories were created.

Operational directories to check include:

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

The exact directory list may be refined during execution, but the report must
explain any excluded path.

## Pass Criteria

The rehearsal passes only if:

- the development workspace starts clean at the reviewed commit;
- the runtime clone starts clean;
- the runtime clone fast-forwards to the reviewed commit;
- the scheduler is not loaded;
- the installed launchd plist is absent;
- package import succeeds;
- semantic-paper CLI help succeeds;
- no request generation or local semantic-paper command is run;
- no workflow, target, activation, lifecycle, reconciliation, order, fill,
  Alpaca, or scheduler evidence is created by the import/help checks;
- no credentials are sourced or read.

## Fail-Closed Conditions

Stop immediately if:

- the development workspace is dirty;
- the runtime clone has local modifications;
- the runtime clone cannot fast-forward;
- launchd reports the Alpaca paper job is loaded;
- the installed Alpaca paper plist exists;
- `.env` would need to be sourced for import or help;
- import or help attempts to create operational evidence;
- any command would require broker credentials or network access.

## Rollback Plan

If the runtime clone was updated and later checks fail:

1. do not run request generation;
2. do not run local semantic paper;
3. capture `git status --short --branch`;
4. capture the failing command and output;
5. leave the runtime clone as-is for review unless the user explicitly
   approves a rollback command;
6. keep launchd unloaded.

No destructive rollback command is pre-approved by this design.

## Explicit Non-Authorization

Approving this design would not authorize executing it. A later stage must
separately approve the runtime-clone copy/import/help rehearsal execution.

Approving or executing that rehearsal would still not authorize generated
requests from the runtime clone, local semantic-paper execution from the
runtime clone, recurring scheduling, Alpaca semantic targets, broker access,
orders, fills, or real-money trading.

