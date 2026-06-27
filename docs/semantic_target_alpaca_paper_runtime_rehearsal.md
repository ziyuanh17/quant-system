# Semantic-Target Alpaca Paper Runtime Rehearsal

Date: 2026-06-26

Status: In review

## Summary

This no-network runtime-clone rehearsal verified that the reviewed
semantic-target Alpaca paper CLI is visible from the runtime clone before any
real paper API interaction.

The rehearsal did not source `.env`, print secrets, construct the real Alpaca
client, contact Alpaca, submit paper orders, run an order-capable command, load
launchd, install a scheduler, or remove runtime evidence.

## Source And Runtime State

Source workspace:

```text
commit: 1232347
status: ## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
```

Runtime clone before fast-forward:

```text
commit: 2614ebc
status:
## main...origin/main
?? data/semantic-target/
```

Runtime fetch and fast-forward:

```text
git -C /Users/mochifufu/Code/quant-system-runtime fetch origin codex/semantic-paper-infra
git -C /Users/mochifufu/Code/quant-system-runtime merge --ff-only origin/codex/semantic-paper-infra
```

Result:

```text
Updating 2614ebc..1232347
Fast-forward
```

Runtime clone after fast-forward:

```text
commit: 1232347
status:
## main...origin/main [ahead 11]
?? data/semantic-target/
```

The untracked `data/semantic-target/` directory is existing runtime evidence
from prior semantic-target work. It was preserved.

## Command Visibility

Runtime import check:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import quant.cli"
```

Result:

```text
exit 0
```

Runtime semantic-target help:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target --help
```

Important output:

```text
alpaca-paper-fake-rehearsal  Run one fake-client semantic-target Alpaca paper rehearsal.
alpaca-paper                 Run one reviewed semantic-target request against Alpaca paper.
```

Runtime Alpaca paper command help:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper --help
```

Important output:

```text
Run one reviewed semantic-target request against Alpaca paper.
--request-path PATH  Reviewed Alpaca paper request JSON to run once. [required]
--from-env           Load Alpaca paper credentials from QUANT_* env.
```

Only help/import commands were run. The order-capable command was not invoked.

## Scheduler And Launchd Evidence

Command:

```text
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Result:

```text
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

## Environment Presence

The runtime shell did not have Alpaca paper variables exported:

```text
QUANT_ALPACA_PAPER_API_KEY=absent
QUANT_ALPACA_PAPER_SECRET_KEY=absent
QUANT_ALPACA_PAPER_ACCOUNT_ID=absent
QUANT_ALPACA_PAPER_URL_OVERRIDE=absent
QUANT_BROKER=absent
QUANT_MAX_ORDER_NOTIONAL=absent
```

No secret values were printed.

## Runtime Directory Snapshot

A before-and-after snapshot was taken around a repeated
`quant semantic-target alpaca-paper --help` command using absolute system
tools. Counts were identical:

```text
before
data/live/orders files=3 dirs=1
data/live/fills files=3 dirs=1
data/live/account_snapshots files=23 dirs=1
data/live/reconciliation files=1 dirs=1
data/semantic-target files=155 dirs=290
data/workflows files=9 dirs=2
data/scheduler absent
data/paper absent
data/web absent
logs files=19 dirs=1

after
data/live/orders files=3 dirs=1
data/live/fills files=3 dirs=1
data/live/account_snapshots files=23 dirs=1
data/live/reconciliation files=1 dirs=1
data/semantic-target files=155 dirs=290
data/workflows files=9 dirs=2
data/scheduler absent
data/paper absent
data/web absent
logs files=19 dirs=1
```

The rehearsal created no new runtime order, fill, snapshot, reconciliation,
semantic-target, workflow, scheduler, paper, web, or log files.

## Notes

An initial directory-count command used bare `wc` and `tr`, which were not on
the runtime shell path:

```text
zsh:1: command not found: wc
zsh:1: command not found: tr
```

That failed command was read-only. The snapshot was rerun with `/usr/bin/wc`,
`/usr/bin/tr`, and `/usr/bin/find`, producing the evidence above.

## Verdict

Passed.

The runtime clone can see the reviewed semantic-target Alpaca paper CLI, the
paper scheduler remains absent, the launchd plist is absent, runtime evidence
was preserved, and help/import checks created no operational files.

## Next Gate

The next stage may prepare for one manual Alpaca paper request. Fresh
preflight evidence must be captured immediately before any real paper API
interaction. That later stage remains one request only and does not authorize
launchd, recurring scheduling, request discovery, non-paper Alpaca behavior,
real-money trading, automatic drift repair, or strategy research.
