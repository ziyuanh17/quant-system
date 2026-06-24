# Supervised Provider Discovery-To-Loop Runtime Copy Rehearsal

This document records the first execution attempt for the runtime-clone
copy/import/help rehearsal and the cleanup of the runtime-clone dirty state.

The rehearsal stopped during read-only preflight. No source was copied, no
runtime clone update was attempted, no import/help command was run from the
runtime clone, no workflow request was executed, no credentials were sourced,
and no broker, Alpaca, paper, semantic-paper, scheduler, launchd, order, or
fill path was touched.

## Reviewed Source

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit before this attempt: `6d2d9d5`

## Read-Only Preflight Evidence

Development workspace:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
6d2d9d5
```

Scheduler state:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

Runtime clone:

```text
git rev-parse --short HEAD
5da3147
```

The runtime clone was not clean:

```text
## main...origin/main
 M site/status.json
 M src/quant/web/docs_index.py
 M src/quant/web/static/css/style.css
 M src/quant/web/static/js/app.js
 M src/quant/web/templates/accounts.html
 M src/quant/web/templates/base.html
 M src/quant/web/templates/decisions.html
 M src/quant/web/templates/history.html
 M src/quant/web/templates/incidents.html
 M src/quant/web/templates/overview.html
 M src/quant/web/templates/system.html
?? data/web/
```

## Initial Decision

The rehearsal initially blocked.

The approved design requires stopping immediately if the runtime clone has
local modifications. Fast-forwarding a dirty runtime clone could overwrite,
mix, or misattribute unrelated work. That would make the rehearsal evidence
untrustworthy even though the command family under review is unrelated to the
web app changes.

## What Did Not Happen

- No `git fetch` was run in the runtime clone.
- No `git merge` was run in the runtime clone.
- No runtime clone file was changed by this rehearsal.
- No package import was attempted from the runtime clone.
- No CLI help command was run from the runtime clone.
- No workflow request was run.
- No launchd job was loaded, unloaded, or kicked.
- No `.env` file was sourced.
- No broker credentials were read.
- No order-capable command was invoked.

## Required Next Step

Resolve the runtime clone dirty state before retrying the copy/import/help
rehearsal. Acceptable options are:

1. review and check in the runtime clone web-app changes through the normal
   source workflow, then fast-forward the runtime clone from Git;
2. move the unrelated runtime clone changes to a separate reviewed worktree;
3. explicitly approve a cleanup plan for those runtime clone changes.

Do not retry the runtime-copy rehearsal until the runtime clone reports a
clean `git status --short --branch`.

## Cleanup

The unrelated runtime-clone web-app changes were preserved in a Git stash:

```text
stash@{0}: On main: runtime-clone-web-app-wip-before-discovery-loop-rehearsal-2026-06-23
```

After stashing, the runtime clone reported clean:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
5da3147

data_web_absent=true
```

No runtime-clone source was deleted. The web-app work can be recovered with
the recorded stash if needed.

## Current Decision

The dirty runtime-clone blocker is resolved. The no-workflow
copy/import/help rehearsal can be retried in a separate step, still under the
same restrictions: no workflow request, no `.env`, no credentials, no launchd,
no scheduler, no paper, no Alpaca, no broker, no orders, and no fills.
