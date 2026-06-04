# Launchd Recurring Schedule Activation

This note records the first activation of the recurring Alpaca paper launchd
schedule.

## Context

- Date: 2026-06-03, America/Los_Angeles
- Activation time: approximately 23:18 PDT
- Runtime clone: `/Users/ziyuan/Code/quant-system-runtime`
- Label: `com.quant-system.alpaca-paper-refresh`
- Installed plist:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- `launchctl bootstrap` attempted: yes
- `launchctl kickstart` attempted: no
- Schedule left loaded: yes
- Next expected natural run: 2026-06-04 12:55 PDT

## Preconditions Checked

The Codex workspace was clean before activation, so the previous activation
design had been reviewed and committed.

The runtime clone was updated to the reviewed commit:

```text
46227369b635d14c3e8d75b02fe94b6ecadacc66
```

Runtime readiness checks showed:

```text
origin = git@github.com:ziyuanh17/quant-system.git
.venv/bin/quant -> /Users/ziyuan/Code/quant-system-runtime/.venv/bin/python
configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist: OK
```

The runtime clone had no tracked changes. Runtime-local files remained ignored:

```text
.env
.venv/
configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
data/
logs/
```

The runtime `.env` safety check showed:

```text
QUANT_BROKER=alpaca-paper
QUANT_MAX_ORDER_NOTIONAL=400
QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=true
QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH=site/status.json
QUANT_ALPACA_PAPER_PUBLISH_STATUS_FAIL_ON_FAILED=false
```

Alpaca paper API key and secret were present. Secret values were not copied
into this note.

Before activation:

```text
launchctl print -> service not found
installed plist -> file not found
```

## Activation

Installed the runtime-local plist into `~/Library/LaunchAgents`:

```bash
cp \
  /Users/ziyuan/Code/quant-system-runtime/configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist \
  /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Made only the installed copy loadable:

```bash
/usr/libexec/PlistBuddy -c 'Set :Disabled false' \
  /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Validated and bootstrapped:

```bash
plutil -lint /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist

launchctl bootstrap gui/501 \
  /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

No `launchctl kickstart` was run.

## Observed launchd State

After activation, launchd reported:

```text
state = not running
runs = 0
last exit code = (never exited)
launchctl blame = (not running)
```

The job points to the runtime clone:

```text
program = /bin/bash
script = /Users/ziyuan/Code/quant-system-runtime/scripts/run_alpaca_paper_refresh.sh
working directory = /Users/ziyuan/Code/quant-system-runtime
stdout path = /Users/ziyuan/Code/quant-system-runtime/logs/launchd-alpaca-paper-refresh.out.log
stderr path = /Users/ziyuan/Code/quant-system-runtime/logs/launchd-alpaca-paper-refresh.err.log
```

The registered calendar triggers are:

```text
Weekday=1 Hour=12 Minute=55
Weekday=2 Hour=12 Minute=55
Weekday=3 Hour=12 Minute=55
Weekday=4 Hour=12 Minute=55
Weekday=5 Hour=12 Minute=55
```

The installed plist remains present:

```text
/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

## Review Plan

After the next natural scheduled run, review:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
launchctl print gui/501/com.quant-system.alpaca-paper-refresh
tail -n 120 logs/launchd-alpaca-paper-refresh.out.log
tail -n 120 logs/launchd-alpaca-paper-refresh.err.log
find logs -maxdepth 1 -type f -name 'alpaca-paper-refresh-*.log' -print
find data/workflows/alpaca-paper-refresh -type f -print
cat data/live/reconciliation/latest.json
```

Expected after the first natural run:

```text
runs >= 1
last exit code = 0
latest wrapper log has preflight_only=false
workflow status = succeeded
reconciliation status = passed
reconciliation differences = 0
site/status.json refreshed if status publishing ran
```

## Rollback

If the first natural scheduled run fails or creates an unexpected paper order,
disable and unload:

```bash
launchctl disable gui/501/com.quant-system.alpaca-paper-refresh
launchctl bootout gui/501/com.quant-system.alpaca-paper-refresh
rm /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Confirm rollback:

```bash
launchctl print gui/501/com.quant-system.alpaca-paper-refresh
ls /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Expected rollback state:

```text
service not found
installed plist not found
```

## Outcome

The recurring Alpaca paper launchd schedule is active and waiting for its first
natural scheduled run. No immediate run occurred during activation.

The next step is to review the first natural scheduled run after
2026-06-04 12:55 PDT.
