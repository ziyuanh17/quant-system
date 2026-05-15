# Operational Observability v1

This guide explains how to inspect the local paper-trading service after it has
started running on a schedule.

The first observability milestone is intentionally read-only:

```text
scheduler run records
  -> paper signal records
  -> persisted paper state
  -> wrapper logs
  -> health report
```

## Health Check

Run:

```bash
quant ops health
```

By default, the command checks:

```text
data/scheduler/latest/
data/paper/signals/
data/paper/state/default.json
data/locks/paper-signal-refresh.lock
logs/
```

Use explicit paths when checking a separate paper account or server layout:

```bash
quant ops health \
  --run-records-dir data/scheduler/latest \
  --signal-records-dir data/paper/signals \
  --state-path data/paper/state/default.json \
  --logs-dir logs \
  --lock-path data/locks/paper-signal-refresh.lock
```

To include paper state reconciliation:

```bash
quant ops health --reconcile-state --initial-cash 100000
```

## Status Meaning

`healthy` means the latest scheduler record, latest paper signal record,
persisted paper state, and logs are all readable.

`degraded` means the system has warnings but no hard failure. Examples include
missing logs or no scheduler records yet. This is useful during first setup,
where a service may not have completed its first run. An active workflow lock is
also degraded because it usually means a run is in progress.

`failed` means a critical operational artifact is missing, invalid, or the
latest scheduler run failed. The command exits with code `1` for this status so
cron, CI, or a future alerting wrapper can detect it. A stale or invalid lock,
or failed paper state reconciliation, is also failed health.

## Output

The command prints a compact report:

```text
Status: healthy
Latest run: succeeded at 2024-01-25 10:01:00+00:00 (...)
Latest signal: action=buy date=2024-01-25 skipped=False (...)
State: cash=1000.0 positions=0 (...)
Logs: logs (1 files)
Lock: status=missing owner=n/a expires_at=n/a (...)
Reconciliation: status=skipped differences=n/a (...)
Issues: 0
```

Each issue is printed with a severity, code, and message. Issue codes are meant
to be stable enough for debugging notes and future alert routing.

## Dashboard Status

Publish the same operational health signal to the static dashboard:

```bash
quant ops publish-status --initial-cash 100000
```

This writes:

```text
site/status.json
```

The dashboard status file is safe to publish through GitHub Pages because it
omits cash, positions, order records, and other sensitive account details. It
only includes high-level run, signal, lock, reconciliation, and issue status.

By default, the command exits successfully even when the health status is
`failed`. That behavior is intentional: a server wrapper can still update the
dashboard with a visible failed state. Add `--fail-on-failed` when the wrapper
should stop on failed health instead.

## Current Limits

Operational Observability v1 does not send notifications, track historical
health, or inspect data freshness. Health can summarize lock and reconciliation
status. The dashboard can show the latest status, but external alert hooks and
historical health records belong in later milestones.
