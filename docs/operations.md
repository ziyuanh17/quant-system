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
logs/
```

Use explicit paths when checking a separate paper account or server layout:

```bash
quant ops health \
  --run-records-dir data/scheduler/latest \
  --signal-records-dir data/paper/signals \
  --state-path data/paper/state/default.json \
  --logs-dir logs
```

## Status Meaning

`healthy` means the latest scheduler record, latest paper signal record,
persisted paper state, and logs are all readable.

`degraded` means the system has warnings but no hard failure. Examples include
missing logs or no scheduler records yet. This is useful during first setup,
where a service may not have completed its first run.

`failed` means a critical operational artifact is missing, invalid, or the
latest scheduler run failed. The command exits with code `1` for this status so
cron, CI, or a future alerting wrapper can detect it.

## Output

The command prints a compact report:

```text
Status: healthy
Latest run: succeeded at 2024-01-25 10:01:00+00:00 (...)
Latest signal: action=buy date=2024-01-25 skipped=False (...)
State: cash=1000.0 positions=0 (...)
Logs: logs (1 files)
Issues: 0
```

Each issue is printed with a severity, code, and message. Issue codes are meant
to be stable enough for debugging notes and future alert routing.

## Current Limits

Operational Observability v1 does not send notifications, track historical
health, or inspect data freshness. Lock files now prevent overlapping refresh
workflow runs, but the health command does not yet summarize lock status.
