# Workflows

Workflows compose existing commands into repeatable operational paths. They are
where the system starts to behave like a server instead of a set of manual CLI
steps.

## Paper Signal Refresh

Run:

```bash
quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
```

This workflow performs one ordered sequence:

```text
fetch provider data
  -> write raw data
  -> write normalized market bars
  -> write validation report and metadata
  -> stop if validation fails
  -> run scheduled paper signal
  -> write workflow record
```

The workflow record is written under:

```text
data/workflows/paper-signal-refresh/
```

It links the refreshed raw data, normalized data, validation report, metadata,
scheduler run records, paper signal records, and paper broker state path. This
linkage is the main reason the workflow exists: debugging a paper decision
should start from one record and trace back to the exact data refresh that
produced it.

## Server Wrapper

For recurring server-style runs, prefer:

```bash
bash scripts/run_paper_signal_refresh.sh
```

This wrapper loads `.env`, runs the refresh workflow, and writes a timestamped
log under `logs/`.

For recurring dry-run rehearsals, use:

```bash
bash scripts/run_dry_run_refresh.sh
```

This wrapper loads `.env`, runs `quant workflow dry-run-refresh`, writes a
timestamped log under `logs/`, and uses `QUANT_DRY_RUN_*` paths for dry-run
orders, dry-run scheduler records, comparison reports, workflow records, and
the dry-run workflow lock.

The older `scripts/run_paper_signal.sh` wrapper still exists for testing a known
static CSV, but it does not refresh data before generating a signal.

## Alpaca Paper Workflow

The scheduled Alpaca paper workflow is designed but not implemented yet. See
[alpaca_paper_workflow.md](alpaca_paper_workflow.md) for the proposed
lock-protected sequence, safety policy, artifact contract, and non-goals.

Do not schedule Alpaca paper broker access until
[alpaca_paper_smoke_runbook.md](alpaca_paper_smoke_runbook.md) has been
reviewed and, ideally, run once against the intended paper account.

## Concurrent Run Safety

The refresh workflow uses a lock file by default:

```text
data/locks/paper-signal-refresh.lock
data/locks/dry-run-refresh.lock
```

If another run already holds the lock, the workflow fails before refreshing data
or touching downstream artifacts. It still writes a failed workflow record, so
the reason is auditable.

Locks become stale after `--lock-stale-after-seconds`, which defaults to `7200`
seconds. A later run can replace a stale lock. This is meant for crash recovery,
not for routinely running multiple workflows at once.

Inspect a lock with:

```bash
cat data/locks/paper-signal-refresh.lock
```

Only remove a lock manually after confirming no workflow process is still
running.

## Current Limits

Data Refresh Workflow v1 refreshes one symbol with one provider and then runs
one strategy. It does not yet reconcile multiple providers, refresh feature
artifacts, or support multi-symbol portfolios.
