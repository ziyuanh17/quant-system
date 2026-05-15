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

The older `scripts/run_paper_signal.sh` wrapper still exists for testing a known
static CSV, but it does not refresh data before generating a signal.

## Current Limits

Data Refresh Workflow v1 refreshes one symbol with one provider and then runs
one strategy. It does not yet reconcile multiple providers, lock concurrent
runs, refresh feature artifacts, or support multi-symbol portfolios.
