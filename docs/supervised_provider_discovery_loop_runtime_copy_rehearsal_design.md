# Supervised Provider Discovery-To-Loop Runtime Copy Rehearsal Design

This document designs the next runtime-clone rehearsal for the manually
started discovery-to-loop dry-run command.

It is a design only. It does not copy source to the runtime clone, run a
workflow, load launchd, use credentials, contact Alpaca, connect to a broker,
or submit orders.

In plain language, this rehearsal would answer one narrow question:

```text
Can the reviewed source be placed in the runtime clone and imported there
without accidentally starting any operational behavior?
```

## Current Reviewed Source

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit before this design bundle: `8e5f7bd`
- Command family under review:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

## Scope

The rehearsal may only:

1. verify the development workspace is clean;
2. verify the recurring Alpaca paper launchd job is not loaded;
3. inspect the runtime clone Git status and current commit;
4. fast-forward the runtime clone to one reviewed commit, if separately
   approved for the execution stage;
5. verify the runtime clone imports the package;
6. verify the runtime clone exposes CLI help for the reviewed command;
7. verify no operational directories were created or modified by the import
   and help checks.

The rehearsal must not:

- run `quant dry-run supervised-provider-discover-finite`;
- create or inspect reviewed workflow request files;
- load, unload, or kickstart launchd;
- source `.env`;
- read broker credentials;
- contact Alpaca;
- run semantic local paper;
- run a scheduler;
- submit or rehearse broker orders.

## Planned Execution Commands

The execution stage should use read-only checks first:

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
git merge --ff-only 8e5f7bd
```

Then verify imports and help only:

```bash
.venv/bin/python -c "import quant; print('quant_import_ok')"
.venv/bin/quant dry-run supervised-provider-discover-finite --help
```

The help command is allowed because it parses CLI metadata and exits before
loading any reviewed request, running discovery, running a finite loop, or
creating workflow evidence.

## Evidence To Capture

The execution report should record:

- development workspace branch, commit, and clean status;
- runtime clone branch, commit before update, and commit after update;
- scheduler not-loaded evidence;
- installed launchd plist absence;
- import command exit code and output;
- CLI help command exit code and output;
- list of operational directories checked before and after.

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
logs
```

The exact directory list may be refined during execution, but the report must
explain any excluded path.

## Pass Criteria

The rehearsal passes only if:

- the development workspace starts clean at the reviewed commit;
- the runtime clone fast-forwards to the reviewed commit;
- the scheduler is not loaded;
- the installed launchd plist is absent;
- package import succeeds;
- command help succeeds;
- no workflow, order, fill, semantic-paper, Alpaca, or scheduler evidence is
  created by the import/help checks;
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

1. do not run any workflow command;
2. capture `git status --short --branch`;
3. capture the failing command and output;
4. leave the runtime clone as-is for review unless the user explicitly
   approves a rollback command;
5. keep launchd unloaded.

No destructive rollback command is pre-approved by this design.

## Explicit Non-Authorization

Approving this design would not authorize executing it. A later stage must
separately approve the runtime-clone copy rehearsal execution.

Approving or executing that rehearsal would still not authorize recurring
scheduling, semantic local paper, Alpaca semantic targets, broker access, or
orders.
