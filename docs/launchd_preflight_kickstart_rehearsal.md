# Launchd Preflight Kickstart Rehearsal

This note records the first launchd-triggered execution rehearsal for the
Alpaca paper wrapper.

## Context

- Date: 2026-06-02, America/Los_Angeles
- Label: `com.quant-system.alpaca-paper-refresh`
- Installed rehearsal copy:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- Installed copy `Disabled`: `false`
- Installed launchd environment:
  `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true`
- `launchctl bootstrap` attempted: yes
- `launchctl kickstart` attempted: yes, once
- Full Alpaca paper workflow reached: no
- Alpaca API reached: no
- Paper order path reached: no

## Expected Behavior

The intended safe path was:

```text
launchd starts /bin/bash
  -> /bin/bash runs scripts/run_alpaca_paper_refresh.sh
  -> wrapper sees QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true
  -> wrapper writes one preflight log
  -> wrapper exits before quant workflow alpaca-paper-refresh
```

## Observed Behavior

The installed plist validated successfully and launchd registered the job with
the expected environment:

```text
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY => true
runs = 0
last exit code = (never exited)
```

After one `launchctl kickstart`, launchd reported:

```text
state = not running
runs = 1
last exit code = 126
```

The launchd stderr log showed:

```text
shell-init: error retrieving current directory: getcwd: cannot access parent directories: Operation not permitted
/bin/bash: /Users/ziyuan/Documents/Codex/2026-05-07/quant-system/scripts/run_alpaca_paper_refresh.sh: Operation not permitted
```

No wrapper preflight log was created. The latest
`logs/alpaca-paper-refresh-*.log` file remained the previous manual wrapper
run, not a new launchd-generated log.

## Safety Outcome

This failed before the wrapper script executed. Because the wrapper did not
start, it could not refresh data, call Alpaca, reconcile account state, publish
dashboard status, or submit a paper order.

The preflight artifact baseline was unchanged:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/workflows/alpaca-paper-refresh
```

The expected `data/live/fills` directory did not exist before the rehearsal and
was not created by the failed kickstart.

After inspection, the launchd job was unloaded and the temporary installed
plist was removed. A follow-up `launchctl print` confirmed the service was no
longer loaded.

## Likely Cause

The failure looks like a macOS filesystem privacy or permission boundary for a
background launchd process trying to execute a script under:

```text
/Users/ziyuan/Documents/Codex/2026-05-07/quant-system
```

The previous controlled load rehearsal proved launchd can register the plist,
working directory, log paths, and calendar triggers. This rehearsal shows the
next boundary: process execution cannot currently access the repo path when
started by launchd.

## Next Step

Diagnose the launchd filesystem permission boundary before another kickstart.
Candidate fixes to evaluate:

- move or mirror the runnable repo outside a macOS protected folder such as
  `Documents`
- grant the appropriate macOS privacy permission for the launchd execution path
- introduce a small wrapper in a less protected path that can enter the repo
  safely
- run the recurring scheduler on a Linux server with `systemd` instead of local
  macOS launchd

Do not retry a full wrapper kickstart until the preflight-only launchd run can
exit with code `0`.

## Follow-Up Resolution

The follow-up diagnosis moved the runnable launchd path outside `Documents` to:

```text
/Users/ziyuan/Code/quant-system-runtime
```

With that runtime clone, the same preflight-only launchd kickstart succeeded:

```text
runs = 1
last exit code = 0
preflight completed without broker submission
```

No trading artifacts were created. See
[launchd_filesystem_permission_diagnosis.md](launchd_filesystem_permission_diagnosis.md).
