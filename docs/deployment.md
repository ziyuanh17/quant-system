# Service Deployment v1

This project is not ready for real-money live trading. This deployment guide is
for running the paper-trading signal loop as a recurring server job.

See [live_broker_adapter.md](live_broker_adapter.md) for the design boundary
that must be satisfied before any real broker deployment is added.

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

For the dry-run rehearsal path, run:

```bash
bash scripts/run_dry_run_refresh.sh
```

That wrapper runs:

```bash
quant workflow dry-run-refresh
```

It refreshes market data, validates it, runs scheduled dry-run signal
execution, compares against the latest paper signal when one exists, and can
publish dashboard health when `QUANT_DRY_RUN_PUBLISH_STATUS_PATH` is set.

For the Alpaca paper rehearsal path, run:

```bash
bash scripts/run_alpaca_paper_refresh.sh
```

That wrapper runs:

```bash
quant workflow alpaca-paper-refresh --from-env
```

It refreshes market data, validates it, submits one actionable signal to the
explicit Alpaca paper client, writes live audit artifacts, and fails if
reconciliation against Alpaca paper broker state does not pass. It does not
retry broker submission automatically.

Set `QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=true` to publish the sanitized
dashboard status after the wrapper finishes. The status file path defaults to
`site/status.json` and can be changed with
`QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH`.

Before installing a recurring paper run, use preflight mode:

```bash
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh
```

Preflight mode writes the resolved log header and exits before refreshing data,
contacting Alpaca, or submitting a paper order. Use it after editing `.env`,
cron, systemd, or path variables so the first broker-connected run is not also
the first configuration check.

## Cron Example

Use absolute paths when installing a cron entry:

```cron
0 14 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_paper_signal_refresh.sh
```

Dry-run wrapper example:

```cron
5 14 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_dry_run_refresh.sh
```

Alpaca paper wrapper example:

```cron
10 14 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_alpaca_paper_refresh.sh
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

For dry-run rehearsals, change `ExecStart` to:

```ini
ExecStart=/usr/bin/bash scripts/run_dry_run_refresh.sh
```

For Alpaca paper rehearsals, change `ExecStart` to:

```ini
ExecStart=/usr/bin/bash scripts/run_alpaca_paper_refresh.sh
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
- dry-run wrappers use distinct `QUANT_DRY_RUN_*` output paths and lock files.
- Alpaca paper wrappers use distinct `QUANT_ALPACA_PAPER_*` output paths and
  lock files.
- Alpaca paper credentials point to the intended paper account, not a
  real-money account.
- the first local wrapper run writes logs, data artifacts, workflow records,
  run records, signal records, and state.
- ignored output directories have enough disk space.

After enabling a recurring run:

- run `quant ops health --reconcile-state --initial-cash 100000` and inspect
  any issue codes.
- run `quant ops publish-status --initial-cash 100000` when the GitHub Pages
  dashboard should show the latest operational status.
- inspect `logs/` after the first scheduled run.
- confirm `data/locks/` is empty after the wrapper exits successfully.
- inspect `data/workflows/paper-signal-refresh/` for workflow records.
- inspect `data/workflows/dry-run-refresh/` for dry-run workflow records.
- inspect `data/dry_run/comparison/latest.json` when dry-run comparison is
  enabled by available paper signal artifacts.
- inspect `data/scheduler/latest/` for run records.
- inspect `data/paper/signals/` for buy/sell/hold/skipped decisions.
- inspect `data/paper/state/` to confirm cash, positions, and the latest
  `.bak` backup are plausible.
- run `quant paper reconcile-state` with the account's starting cash to confirm
  persisted state matches the signal audit trail.

See [operations.md](operations.md) for health check behavior.

## Dashboard Publishing

The static dashboard reads:

```text
site/status.json
```

Generate that file with:

```bash
quant ops publish-status --initial-cash 100000
```

The file is intentionally sanitized for GitHub Pages. It includes health,
latest run, latest signal, lock, reconciliation, issue summaries, and Alpaca
paper decision status when requested with `--check-alpaca-paper`. Alpaca paper
status includes signal action, broker-submission outcome, and artifact counts,
but not cash, positions, account IDs, secrets, raw broker payloads, or raw order
details.

If a server job commits and pushes changes under `site/`, the existing GitHub
Pages workflow can publish the updated dashboard. Keep that publishing step
separate from trading execution until the real-money trading boundary is
designed.

## Current Limits

Service Deployment v1 is intentionally small.

It does not yet provide:

- process supervision beyond cron or systemd
- alerts or notifications
- cloud deployment templates
- real broker connectivity

Those belong in later milestones after the local service contract is stable.
