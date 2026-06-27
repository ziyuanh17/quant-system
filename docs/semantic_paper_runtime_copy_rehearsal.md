# Semantic-Paper Runtime Copy/Import/Help Rehearsal

This document records the runtime-clone import/help-only rehearsal for the
reviewed semantic-paper command family.

The rehearsal fast-forwarded the clean runtime clone to reviewed source, then
verified package import and semantic-paper CLI help only. It did not generate
requests, inspect request files, run local semantic paper, load launchd, source
credentials, contact Alpaca, connect to a broker, or submit orders.

## Reviewed Source

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit: `2614ebc`
- Runtime clone commit before update: `56b45cc`
- Runtime clone commit after update: `2614ebc`

## Preflight Evidence

Development workspace:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
2614ebc
```

Scheduler state:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501

installed_plist_absent=true
```

Runtime clone before update:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
56b45cc
```

Operational directory baseline before import/help:

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
logs exists
```

Existing `__pycache__` directory count before import/help:

```text
422
```

## Runtime Clone Update

The runtime clone fetched `origin/main` and fast-forwarded:

```text
git fetch origin main
56b45cc..2614ebc  main -> origin/main

git merge --ff-only 2614ebc
Fast-forward
```

The fast-forward brought reviewed source and checked-in research evidence into
the runtime clone. It did not run workflow commands or create local runtime
outputs.

## Import And Help Checks

All checks used `PYTHONDONTWRITEBYTECODE=1`.

Package import:

```text
.venv/bin/python -c "import quant; print('quant_import_ok')"
quant_import_ok
```

Semantic-paper command group help:

```text
.venv/bin/quant semantic-paper --help

Commands:
  activated-target
  prepare-momentum-request
  inspect-activated-target
```

Request generator help:

```text
.venv/bin/quant semantic-paper prepare-momentum-request --help

Prepare a reviewed local-paper request from legacy momentum.
```

Request inspection help:

```text
.venv/bin/quant semantic-paper inspect-activated-target --help

Explain and validate a local semantic-paper request without writing.
```

Local semantic-paper execution help:

```text
.venv/bin/quant semantic-paper activated-target --help

Run one reviewed activated target through local semantic paper.
```

These help checks parse command metadata and exit. They do not load market
data, request paths, activation artifacts, broker credentials, or runtime data.

## Post-Check Evidence

Runtime clone after import/help:

```text
git status --short --branch
## main...origin/main

git rev-parse --short HEAD
2614ebc
```

Operational directories after import/help:

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
logs exists
```

Existing `__pycache__` directory count after import/help:

```text
422
```

## Result

The runtime-clone import/help-only rehearsal passed.

The reviewed semantic-paper command family can be imported and displayed from
the runtime clone without creating semantic-target outputs, local paper outputs,
scheduler outputs, orders, fills, or Git working-tree changes.

## Explicit Non-Authorization

This success does not authorize generated requests from the runtime clone,
local semantic-paper execution from the runtime clone, recurring scheduling,
Alpaca semantic targets, broker access, orders, fills, or real-money trading.

