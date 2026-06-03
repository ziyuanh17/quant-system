# Launchd Triggered Execution Rehearsal Design

This design describes the first launchd-triggered execution test for the
Alpaca paper wrapper. It is intentionally not a full trading workflow yet.

## Goal

Prove that launchd can start the wrapper process and write logs without
refreshing market data, touching Alpaca, reconciling broker state, or
submitting a paper order.

The first triggered rehearsal should use wrapper preflight mode:

```text
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true
```

The wrapper already treats this as a safe branch: it resolves configuration,
writes a timestamped log, prints the log, and exits before running
`quant workflow alpaca-paper-refresh`.

## Non-Goals

This rehearsal must not:

- run the full Alpaca paper refresh workflow
- call Alpaca APIs
- refresh market data
- write order, fill, snapshot, or reconciliation artifacts
- publish dashboard status
- leave launchd loaded after inspection
- enable real-money trading

## Recommended Sequence

Start from the already localized plist:

```text
configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Before loading, install a temporary copy:

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

Add preflight-only launchd environment to the installed copy:

```bash
/usr/libexec/PlistBuddy -c 'Add :EnvironmentVariables dict' \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist

/usr/libexec/PlistBuddy -c \
  'Add :EnvironmentVariables:QUANT_ALPACA_PAPER_PREFLIGHT_ONLY string true' \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Validate the installed copy:

```bash
plutil -lint ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Bootstrap:

```bash
launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Inspect before triggering:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
launchctl blame gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Expected before trigger:

```text
state = not running
runs = 0
last exit code = (never exited)
```

Kickstart only after confirming `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true` is in
the installed plist:

```bash
launchctl kickstart \
  gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Inspect after trigger:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Expected after trigger:

```text
runs = 1
last exit code = 0
```

Then unload and remove the installed copy:

```bash
launchctl bootout gui/$(id -u)/com.quant-system.alpaca-paper-refresh
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

## Artifact Review

The only expected repo artifact from this rehearsal is a new wrapper log:

```text
logs/alpaca-paper-refresh-*.log
```

The log should contain:

```text
preflight_only=true
preflight completed without broker submission
completed_at=...
```

The rehearsal should not create new files under:

```text
data/live/orders/
data/live/fills/
data/live/account_snapshots/
data/live/reconciliation/
data/workflows/alpaca-paper-refresh/
```

If any of those artifacts change during the preflight-only rehearsal, stop and
diagnose before attempting a full launchd-triggered wrapper run.

## Safety Checks

Before `kickstart`, verify:

- the installed plist has `Disabled=false`
- the installed plist has
  `EnvironmentVariables:QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true`
- launchd reports `runs = 0`
- `launchctl blame` reports `(not running)`
- the current time is not near the configured calendar trigger

After `kickstart`, verify:

- launchd reports the wrapper exited
- `last exit code` is `0`
- the log says preflight completed without broker submission
- no Alpaca paper order artifacts were created
- the installed plist is unloaded and removed

## Why Preflight First

This is the smallest meaningful launchd execution test. It checks the launchd
process boundary, working directory, environment injection, `.env` loading, and
logging path without coupling the result to provider data, broker connectivity,
strategy output, or order safety.

Only after this passes should the project consider a separate full
launchd-triggered wrapper rehearsal.
