# Launchd Controlled Load Rehearsal

This note records the first successful load-only rehearsal for the Alpaca paper launchd job.

## Context

- Date: 2026-06-02, America/Los_Angeles
- Local time at rehearsal start: 20:38 PDT
- Label: `com.quant-system.alpaca-paper-refresh`
- Installed rehearsal copy:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- Local review copy:
  `configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist`
- Installed copy `Disabled`: `false`
- Local review copy `Disabled`: `true`
- `launchctl kickstart` attempted: no
- Manual launchd run attempted: no
- Scheduled run occurred: no

## Purpose

The previous diagnosis showed that `Disabled=true` prevents `launchctl
bootstrap` on this macOS setup. This rehearsal tested the next safe state:
make only the installed copy loadable with `Disabled=false`, register it with
launchd, inspect its state, then unload it immediately.

This verifies launchd registration without manually triggering the Alpaca paper
workflow.

## Commands

Install a temporary launchd copy:

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

Validate:

```bash
plutil -lint ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Bootstrap:

```bash
launchctl bootstrap gui/501 \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Inspect:

```bash
launchctl print gui/501/com.quant-system.alpaca-paper-refresh
launchctl blame gui/501/com.quant-system.alpaca-paper-refresh
```

Unload:

```bash
launchctl bootout gui/501/com.quant-system.alpaca-paper-refresh
```

Remove the installed copy:

```bash
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

## Observed launchctl State

The actual label bootstrapped successfully.

Key inspection results:

```text
state = not running
program = /bin/bash
working directory = /Users/ziyuan/Documents/Codex/2026-05-07/quant-system
runs = 0
last exit code = (never exited)
launchctl blame = (not running)
```

The registered event triggers matched the intended weekday schedule:

```text
Weekday=1 Hour=12 Minute=55
Weekday=2 Hour=12 Minute=55
Weekday=3 Hour=12 Minute=55
Weekday=4 Hour=12 Minute=55
Weekday=5 Hour=12 Minute=55
```

## Cleanup

After inspection, the job was unloaded successfully. A follow-up
`launchctl print` returned:

```text
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
```

The temporary installed plist under `~/Library/LaunchAgents` was removed.

## Outcome

The actual Alpaca paper launchd label can be registered when the installed
plist is intentionally made loadable with `Disabled=false`.

No manual launchd run was triggered, no scheduled run occurred, and no Alpaca
order path was invoked by launchd.

The next step should design a safe launchd-triggered execution rehearsal before
using `launchctl kickstart` on the real wrapper.
