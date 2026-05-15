# Service Deployment v1

This project is not ready for real-money live trading. This deployment guide is
for running the paper-trading signal loop as a recurring server job.

The goal of this version is operational clarity:

```text
configuration
  -> command wrapper
  -> logs
  -> scheduler run records
  -> paper signal records
  -> persisted paper state
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
- `QUANT_DATA`: market-bar CSV used for signal generation
- `QUANT_QUANTITY`: paper order quantity for actionable signals
- `QUANT_STATE_PATH`: persisted paper account state
- `QUANT_SIGNAL_OUTPUT_DIR`: paper signal audit records
- `QUANT_RUN_OUTPUT_DIR`: scheduler run records
- `QUANT_LOG_DIR`: wrapper logs

Use a different `QUANT_STATE_PATH` for each separate paper account or
experiment. Reusing a state path means the runs share one paper account.

## Local Run

Run the wrapper:

```bash
bash scripts/run_paper_signal.sh
```

The wrapper loads `.env` when present, appends console output to a timestamped
log file, and runs:

```bash
quant schedule paper-signal
```

The paper signal command is idempotent for repeated signals. If it sees the
same strategy, symbol, signal date, and action again, it writes a skipped audit
record instead of placing a duplicate paper order.

## Cron Example

Use absolute paths when installing a cron entry:

```cron
0 14 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_paper_signal.sh
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
ExecStart=/usr/bin/bash scripts/run_paper_signal.sh
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
- `.env` points to the intended data file.
- `QUANT_STATE_PATH` is unique to the paper account.
- the data file exists and has current normalized market bars.
- validation is enabled unless debugging a known data issue.
- the first local wrapper run writes logs, run records, signal records, and state.
- ignored output directories have enough disk space.

After enabling a recurring run:

- inspect `logs/` after the first scheduled run.
- inspect `data/scheduler/latest/` for run records.
- inspect `data/paper/signals/` for buy/sell/hold/skipped decisions.
- inspect `data/paper/state/` to confirm cash and positions are plausible.

## Current Limits

Service Deployment v1 is intentionally small.

It does not yet provide:

- process supervision beyond cron or systemd
- alerts or notifications
- lock files for concurrent runs
- atomic state writes
- data refresh orchestration
- cloud deployment templates
- real broker connectivity

Those belong in later milestones after the local service contract is stable.
