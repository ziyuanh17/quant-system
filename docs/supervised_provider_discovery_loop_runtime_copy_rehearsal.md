# Supervised Provider Discovery-To-Loop Runtime Copy/Import/Help Rehearsal

This document records the runtime-clone copy/import/help rehearsal and the
cleanup of the runtime-clone dirty state that initially blocked it.

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

## Successful Retry

After cleanup, the rehearsal was retried from clean worktrees.

Development workspace:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
1a31de6
```

Runtime clone before update:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
5da3147
```

Scheduler state remained unloaded:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

The runtime clone then fetched and fast-forwarded to the reviewed source:

```text
git fetch origin main
5da3147..1a31de6  main -> origin/main

git merge --ff-only 1a31de6
Fast-forward
```

Runtime clone after update:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
1a31de6
```

The package import check passed with bytecode writing disabled:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import quant; print('quant_import_ok')"
quant_import_ok
```

The command help check passed with bytecode writing disabled:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant dry-run supervised-provider-discover-finite --help

Usage: quant dry-run supervised-provider-discover-finite [OPTIONS]

Run one reviewed discovery-to-finite supervised-provider request.

Options:
  --request-path PATH  Exact reviewed discovery-to-finite request. [required]
  --help               Show this message and exit.
```

Operational directory check after import/help:

```text
data/live/orders exists
data/live/fills exists
data/live/account_snapshots exists
data/live/reconciliation exists
data/semantic-target absent
data/workflows exists
data/scheduler absent
data/paper absent
data/web absent
```

The existing `data/live/*` and `data/workflows` directories are historical
runtime artifacts. This rehearsal did not run workflows or create new Git
working-tree changes. The runtime clone remained clean after import/help:

```text
git status --short --branch
## main...origin/main
```

No new `__pycache__` directories were found from the import/help checks.

The unrelated web-app work remains preserved in:

```text
stash@{0}: On main: runtime-clone-web-app-wip-before-discovery-loop-rehearsal-2026-06-23
```

## Final Decision

The no-workflow runtime-clone copy/import/help rehearsal passed.

This success does not authorize running `supervised-provider-discover-finite`
from the runtime clone. It also does not authorize workflow execution,
credentials, launchd, recurring scheduling, semantic local paper, Alpaca,
broker access, orders, or fills.
