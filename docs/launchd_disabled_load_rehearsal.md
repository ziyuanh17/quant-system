# Launchd Disabled Load Rehearsal

This note records the first attempt to load the Alpaca paper launchd job while
the plist still had `Disabled=true`.

## Context

- Date: 2026-06-01 America/Los_Angeles
- Label: `com.quant-system.alpaca-paper-refresh`
- Template: `configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example`
- Local copy: `configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist`
- Installed rehearsal copy:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- launchd `Disabled`: `true`
- launchd enable attempted: no
- launchd kickstart attempted: no
- scheduled run occurred: no

## Template Correction

The checked-in template originally represented weekday scheduling as one
`StartCalendarInterval` dictionary containing a `Weekday` array. The local
macOS launchd documentation describes recurring calendar schedules as either
one dictionary of integer fields or an array of dictionaries, so the template
was corrected to use five explicit dictionaries:

```text
Weekday=1 Hour=12 Minute=55
Weekday=2 Hour=12 Minute=55
Weekday=3 Hour=12 Minute=55
Weekday=4 Hour=12 Minute=55
Weekday=5 Hour=12 Minute=55
```

That shape is easier to inspect and avoids relying on launchd accepting an
array value inside a calendar field.

## Checks Performed

Validated the localized plist syntax:

```text
plutil -lint configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Result:

```text
OK
```

Confirmed the service was not loaded before the rehearsal:

```text
launchctl print gui/501/com.quant-system.alpaca-paper-refresh
```

Result:

```text
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
```

Attempted to bootstrap the disabled repo-local plist:

```text
launchctl bootstrap gui/501 \
  /Users/ziyuan/Documents/Codex/2026-05-07/quant-system/configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Result:

```text
Bootstrap failed: 5: Input/output error
```

Copied the same disabled plist to `~/Library/LaunchAgents`, validated that
installed copy with `plutil`, and attempted the normal user-agent bootstrap
path:

```text
launchctl bootstrap gui/501 \
  /Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Result:

```text
Bootstrap failed: 5: Input/output error
```

Queried the unified log for the label. macOS Background Task Management saw
the plist as a legacy agent with `/bin/bash` as the executable and the wrapper
script as the argument, but the log did not show a more specific launchd
rejection reason during this pass.

## Cleanup

After the failed bootstrap attempts, `launchctl print` still reported that the
service was not loaded. The temporary installed plist was then removed from
`~/Library/LaunchAgents`.

The ignored local plist under `configs/launchd/*.local.plist` remains available
for future diagnosis, but there is no loaded launchd service and no enabled
recurring schedule from this rehearsal.

## Outcome

The disabled load rehearsal did not complete successfully because launchd
returned error 5 during bootstrap. This is a controlled blocker, not a trading
failure: no launchd enable action was attempted, no kickstart was attempted,
and no Alpaca order path was invoked by launchd.

The next step should diagnose the launchd bootstrap failure before any attempt
to enable or run the job through launchd.

## Follow-Up Diagnosis

The follow-up diagnosis found that `Disabled=true` was the cause of bootstrap
error 5 on this macOS setup. A minimal job with `Disabled=true` failed the same
way, while minimal jobs with no `Disabled` key or `Disabled=false` loaded
successfully without running.

See [launchd_bootstrap_failure_diagnosis.md](launchd_bootstrap_failure_diagnosis.md).
