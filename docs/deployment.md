# Service Deployment v1

This project is not ready for real-money live trading. This deployment guide is
for running the paper-trading signal loop as a recurring server job.

The goal of this version is operational clarity:

```text
configuration
  -> command wrapper
  -> logs
  -> data refresh artifacts
  -> scheduler run records
  -> paper signal records
  -> persisted paper state
  -> workflow records
```

## Configuration

Copy the example environment file:

```bash
cp .env.example .env
```

Important settings:

- `QUANT_CMD`: path to the CLI, usually `.venv/bin/quant`
- `QUANT_STRATEGY`: strategy name, currently `momentum`
- `QUANT_SYMBOL`: symbol to trade
- `QUANT_PROVIDER`: market-data provider, currently `yfinance`
- `QUANT_START`: refresh start date
- `QUANT_END`: optional refresh end date
- `QUANT_DATA`: market-bar CSV used for signal generation
- `QUANT_QUANTITY`: paper order quantity for actionable signals
- `QUANT_STATE_PATH`: persisted paper account state
- `QUANT_SIGNAL_OUTPUT_DIR`: paper signal audit records
- `QUANT_RUN_OUTPUT_DIR`: scheduler run records
- `QUANT_WORKFLOW_OUTPUT_DIR`: refresh workflow records
- `QUANT_LOCK_PATH`: lock file that prevents overlapping refresh runs
- `QUANT_LOCK_STALE_AFTER_SECONDS`: seconds before a lock can be replaced
- `QUANT_LOG_DIR`: wrapper logs

Use a different `QUANT_STATE_PATH` for each separate paper account or
experiment. Reusing a state path means the runs share one paper account.

## Local Run

Run the wrapper:

```bash
bash scripts/run_paper_signal_refresh.sh
```

The wrapper loads `.env` when present, appends console output to a timestamped
log file, and runs:

```bash
quant workflow paper-signal-refresh
```

The workflow refreshes market data, validates it, writes lineage artifacts, and
only then runs the paper signal scheduler. The paper signal command remains
idempotent for repeated signals. If it sees the same strategy, symbol, signal
date, and action again, it writes a skipped audit record instead of placing a
duplicate paper order.

## Cron Example

Use absolute paths when installing a cron entry:

```cron
0 14 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_paper_signal_refresh.sh
```

The example above runs once per weekday. Choose a time that matches the data
refresh policy for the input CSV. Do not schedule paper execution before the
data file has been refreshed and validated.

## systemd Example

Example service:

```ini
[Unit]
Description=Quant paper signal run

[Service]
Type=oneshot
WorkingDirectory=/absolute/path/to/quant-system
ExecStart=/usr/bin/bash scripts/run_paper_signal_refresh.sh
```

Example timer:

```ini
[Unit]
Description=Run quant paper signal on weekdays

[Timer]
OnCalendar=Mon..Fri 14:00
Persistent=true

[Install]
WantedBy=timers.target
```

Treat these snippets as templates. The exact path to `bash`, working directory,
and schedule should match the target machine.

## Operational Checklist

Before enabling a recurring run:

- `make check` passes.
- `.env` points to the intended provider, symbol, and refresh start date.
- `QUANT_STATE_PATH` is unique to the paper account.
- `QUANT_LOCK_PATH` is unique to the workflow/account being scheduled.
- the first local wrapper run writes logs, data artifacts, workflow records,
  run records, signal records, and state.
- ignored output directories have enough disk space.

After enabling a recurring run:

- run `quant ops health` and inspect any issue codes.
- inspect `logs/` after the first scheduled run.
- confirm `data/locks/` is empty after the wrapper exits successfully.
- inspect `data/workflows/paper-signal-refresh/` for workflow records.
- inspect `data/scheduler/latest/` for run records.
- inspect `data/paper/signals/` for buy/sell/hold/skipped decisions.
- inspect `data/paper/state/` to confirm cash, positions, and the latest
  `.bak` backup are plausible.
- run `quant paper reconcile-state` with the account's starting cash to confirm
  persisted state matches the signal audit trail.

See [operations.md](operations.md) for health check behavior.

## Current Limits

Service Deployment v1 is intentionally small.

It does not yet provide:

- process supervision beyond cron or systemd
- alerts or notifications
- cloud deployment templates
- real broker connectivity

Those belong in later milestones after the local service contract is stable.
