# Launchd Bootstrap Failure Diagnosis

This note records the diagnosis for the launchd bootstrap error found during
the disabled load rehearsal.

## Symptom

The Alpaca paper launchd plist validated with `plutil`, but `launchctl`
returned:

```text
Bootstrap failed: 5: Input/output error
```

The failure happened for both the repo-local plist and a copy installed under
`~/Library/LaunchAgents`.

## Root Cause

On this macOS setup, a launchd job with `Disabled=true` cannot be bootstrapped.

The local `launchctl` manual explains the operational state this way:

```text
Once a service is disabled, it cannot be loaded in the specified domain until it is once again enabled.
```

The `Disabled` plist key is therefore useful as a fail-closed review marker in
the checked-in template, but it is not a way to load a dormant job for
inspection. Before a real `launchctl bootstrap`, the localized plist must be
changed to `Disabled=false` or have the `Disabled` key removed.

## Evidence

All probes were performed without `launchctl enable`, without `launchctl
kickstart`, and without a launchd-triggered Alpaca workflow run.

| Probe | Key Difference | Bootstrap Result | Runs |
| --- | --- | --- | --- |
| Minimal `/bin/echo` with `Disabled=true` | Disabled by plist | Failed with error 5 | Not loaded |
| Minimal `/bin/echo` without `Disabled` | No schedule, no disabled key | Succeeded | `0` |
| Minimal `/bin/echo` with calendar schedule | Weekday 12:55 schedule shape | Succeeded | `0` |
| Real-shaped Alpaca wrapper plist without `Disabled` | Wrapper path, working dir, logs, calendar schedule | Succeeded | `0` |
| Minimal `/bin/echo` with `Disabled=false` | Explicitly loadable plist | Succeeded | `0` |

The successful real-shaped probe showed launchd accepting:

```text
program = /bin/bash
working directory = /Users/ziyuan/Documents/Codex/2026-05-07/quant-system
stdout path = logs/launchd-alpaca-paper-refresh.out.log
stderr path = logs/launchd-alpaca-paper-refresh.err.log
runs = 0
```

It also showed five calendar triggers, one for each weekday at 12:55.

## Interpretation

The error was not caused by:

- the wrapper path
- the working directory
- stdout/stderr log paths
- the corrected weekday calendar shape
- the repo-local plist path

The failing variable was `Disabled=true`.

## Safety Outcome

The diagnostic jobs were unloaded after inspection. The actual Alpaca paper
launchd label was not enabled or kickstarted, and launchd did not submit any
Alpaca order.

## Operational Rule

Use `Disabled=true` only before the job is ready to load. It is a safety
marker, not a loadable dormant mode.

The safe sequence is:

```text
keep checked-in template Disabled=true
  -> localize paths
  -> run preflight
  -> run one manual full wrapper cycle
  -> review dashboard and artifacts
  -> set Disabled=false in the installed plist
  -> bootstrap
  -> inspect launchctl state
  -> bootout if this is still only a rehearsal
```

Do not run `launchctl kickstart` until a separate manual launchd execution
review is explicitly approved.
