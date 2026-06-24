# Supervised Provider Discovery-To-Loop Runtime Command Rehearsal

This document records the runtime-clone no-network actual-command rehearsal
for the manually started discovery-to-loop dry-run command.

The rehearsal used synthetic reviewed inputs generated under `/tmp`. It did
not use `.env`, credentials, launchd, scheduler, semantic local paper, Alpaca,
broker access, orders, or fills.

## Reviewed State

- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`
- Reviewed source commit: `8d1398a`
- Runtime clone stash preserved:
  `stash@{0}: On main: runtime-clone-web-app-wip-before-discovery-loop-rehearsal-2026-06-23`

Preflight confirmed:

```text
development git status: ## main...origin/main
development commit: 8d1398a
runtime git status: ## main...origin/main
runtime commit: 8d1398a
launchd service: not found
installed_plist_absent=true
```

## Runtime Operational Directory Snapshot

Before and after the rehearsal, the runtime operational directory snapshot was
the same:

```text
data/live/orders 1781193481
data/live/fills 1781249658
data/live/account_snapshots 1781294101
data/live/reconciliation 1780207045
data/semantic-target absent
data/workflows 1781149085
data/scheduler absent
data/paper absent
data/web absent
logs 1781294100
```

The existing `data/live/*`, `data/workflows`, and `logs` paths are historical
runtime paths. The rehearsal did not modify them.

## Rehearsal Command

The rehearsal ran from the runtime clone with bytecode writing disabled:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python
```

It invoked
`run_supervised_provider_discovery_loop_command_rehearsal(...)` with:

```text
output_root=/tmp/quant-runtime-discovery-loop-command-rehearsal
rehearsal_id=runtime-discovery-loop-command-rehearsal
quant_executable_path=.venv/bin/quant
```

The report path was:

```text
/tmp/quant-runtime-discovery-loop-command-rehearsal/reports/runtime-discovery-loop-command-rehearsal.json
```

## Result

The report verified successfully:

```text
evaluated_at=2026-06-24T05:06:01.052954+00:00
passed=True
scenarios=5
source_files=126
observations=6
composition_records=4
evidence_paths=1519
prohibited=0
```

Post-checks confirmed:

```text
runtime git status: ## main...origin/main
runtime commit: 8d1398a
new __pycache__ directories: none
```

## Boundary

This rehearsal proves the runtime clone can run the existing synthetic
actual-command rehearsal with evidence rooted under `/tmp`.

It does not authorize:

- running hand-authored reviewed request files;
- writing runtime `data` or `logs`;
- sourcing `.env`;
- reading credentials;
- loading, unloading, or kickstarting launchd;
- recurring scheduling;
- semantic local paper;
- Alpaca;
- broker access;
- orders or fills.
