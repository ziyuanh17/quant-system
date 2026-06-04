# Launchd Recurring Schedule Activation Design

This design describes when and how to leave the Alpaca paper launchd schedule
loaded for recurring unattended runs.

It does not activate the schedule. Activation should be a separate reviewed
step.

## Goal

Move from one-shot launchd rehearsals to a recurring Alpaca paper schedule that
runs from the runtime clone:

```text
/Users/ziyuan/Code/quant-system-runtime
```

The first recurring schedule should run once per market weekday at:

```text
12:55 PM America/Los_Angeles
```

It should remain Alpaca paper only, use tiny sizing, publish dashboard status
only if intentionally configured, and have a clear rollback path.

## Preconditions

Do not activate the recurring schedule unless all of these are true:

- reviewed commits have been pushed from the Codex workspace
- runtime clone is updated to the intended commit
- runtime clone has no unexpected tracked changes
- runtime `.env` is paper-only
- runtime `.venv/bin/quant` points to the runtime clone
- runtime local launchd plist points to the runtime clone
- `QUANT_MAX_ORDER_NOTIONAL` is intentionally small
- the latest preflight launchd kickstart succeeded
- the latest full launchd wrapper rehearsal succeeded
- reconciliation passed with zero differences
- no unexpected Alpaca paper order is open
- the user is willing to review the first scheduled run after 12:55 PM

## Runtime Update Policy

The Codex workspace remains the development and review workspace:

```text
/Users/ziyuan/Documents/Codex/2026-05-07/quant-system
```

The runtime clone is what launchd executes:

```text
/Users/ziyuan/Code/quant-system-runtime
```

Before activation, update the runtime clone only from reviewed Git history:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
git pull origin main
```

If `pyproject.toml`, `uv.lock`, or dependency-related files changed, refresh
the runtime virtualenv:

```bash
.venv/bin/python -m pip install -e ".[broker-alpaca]"
```

Do not hand-edit tracked source files in the runtime clone. Runtime-local files
should remain ignored:

```text
.env
.venv/
configs/launchd/*.local.plist
logs/
data/
```

## Activation Sequence

Run these commands from the runtime clone:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
```

Verify readiness:

```bash
git status --short --ignored
git remote -v
head -n 3 .venv/bin/quant
plutil -lint configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
ls ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Install the launchd plist:

```bash
cp \
  configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Make only the installed copy loadable:

```bash
/usr/libexec/PlistBuddy -c 'Set :Disabled false' \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Validate and load:

```bash
plutil -lint ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist

launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Inspect:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
launchctl blame gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Expected immediately after activation:

```text
state = not running
runs = 0
last exit code = (never exited)
event triggers include Weekday=1..5 Hour=12 Minute=55
```

Do not run `launchctl kickstart` during activation. The next run should be the
natural scheduled run.

## First Scheduled Run Review

After the next scheduled 12:55 PM run, review:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
tail -n 120 logs/launchd-alpaca-paper-refresh.out.log
tail -n 120 logs/launchd-alpaca-paper-refresh.err.log
find logs -maxdepth 1 -type f -name 'alpaca-paper-refresh-*.log' -print
find data/workflows/alpaca-paper-refresh -type f -print
cat data/live/reconciliation/latest.json
```

Expected:

```text
runs >= 1
last exit code = 0
latest wrapper log has preflight_only=false
workflow status = succeeded
reconciliation status = passed
reconciliation differences = 0
```

If dashboard publishing is enabled, also review:

```text
site/status.json
```

Expected dashboard fields:

```text
alpaca_paper_workflow_status = succeeded
alpaca_paper_reconciliation_status = passed
alpaca_paper_reconciliation_difference_count = 0
```

## Monitoring Checklist

For each scheduled run, review:

- launchd `last exit code`
- latest wrapper log
- latest workflow record
- latest signal action
- broker submission attempted/skipped reason
- reconciliation status and difference count
- account snapshot timestamp
- Alpaca paper dashboard for unexpected open orders
- dashboard status file, if publishing is enabled

For the first week, review every scheduled run manually. After several clean
runs, review frequency can be reduced, but do not reduce review before the
system has observed both `hold` and actionable signal paths safely.

## Rollback

Disable future starts:

```bash
launchctl disable gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Unload the current job:

```bash
launchctl bootout gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Remove the installed plist:

```bash
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Confirm rollback:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
ls ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Expected:

```text
service not found
installed plist not found
```

## Stop Conditions

Disable and unload the schedule immediately if:

- launchd exits nonzero
- wrapper log is missing
- workflow status is not `succeeded`
- reconciliation status is not `passed`
- reconciliation differences are nonzero
- Alpaca shows an unexpected open paper order
- broker submission occurs without a matching local order artifact
- order notional exceeds `QUANT_MAX_ORDER_NOTIONAL`
- data validation fails
- the runtime clone has unexpected tracked changes
- `.env` no longer says `QUANT_BROKER=alpaca-paper`

## Dashboard Publishing Decision

Dashboard publishing is useful for recurring operation, but it should not hide
the local artifact review. Recommended first activation:

```text
QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=true
QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH=site/status.json
QUANT_ALPACA_PAPER_PUBLISH_STATUS_FAIL_ON_FAILED=false
```

Keep `FAIL_ON_FAILED=false` for the first activation so the workflow record and
logs remain the primary source of truth. Escalate this later after failure
handling is better rehearsed.

## Missed Run Handling

If the machine is asleep, powered off, or logged out at 12:55 PM, the LaunchAgent
may miss the run. The first policy is to record and review the miss, not to
auto-catch-up with a delayed broker-connected run.

If a run is missed:

1. Confirm launchd is still loaded.
2. Confirm no run artifacts were created.
3. Decide manually whether to run a one-shot wrapper rehearsal later.
4. Do not add automatic catch-up until market-hours and stale-signal handling
   are explicitly designed.

## Activation Outcome Criteria

Activation is successful only if:

- launchd remains loaded with the weekday 12:55 schedule
- no immediate run occurs at activation time
- first natural scheduled run exits `0`
- workflow succeeds
- reconciliation passes
- no unexpected paper order appears
- the user reviews the first scheduled run artifacts

If any condition fails, unload the job and return to one-shot rehearsals.
