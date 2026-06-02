# Launchd Manual Wrapper Review

This note records the manual full Alpaca paper wrapper review after local
launchd plist preflight. It did not load, enable, or kickstart launchd.

## Summary

- Date: 2026-06-01, America/Los_Angeles
- Wrapper: `scripts/run_alpaca_paper_refresh.sh`
- Launchd local plist: `configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist`
- Launchd `Disabled`: `true`
- Launchd load attempted: no
- Launchd enable attempted: no
- Launchd kickstart attempted: no
- Workflow status: `succeeded`
- Latest signal: `hold`
- Broker submission attempted: `false`
- Broker submission skipped reason: `latest strategy signal is hold`
- Order artifacts created by this run: 0
- Fill artifacts created by this run: 0
- Account snapshot artifacts created by this run: 1
- Reconciliation status: `passed`
- Reconciliation differences: 0
- Dashboard status: `healthy`
- Dashboard issues: 0

## Commands

Manual full wrapper cycle:

```bash
bash scripts/run_alpaca_paper_refresh.sh
```

Alpaca-only dashboard publish:

```bash
quant ops publish-status \
  --no-check-paper-service \
  --no-check-comparison \
  --check-alpaca-paper \
  --alpaca-paper-workflow-records-dir data/workflows/alpaca-paper-refresh \
  --alpaca-paper-reconciliation-report-path data/live/reconciliation/latest.json
```

## Reviewed Artifacts

```text
logs/alpaca-paper-refresh-20260602T051438Z.log
data/workflows/alpaca-paper-refresh/de7b9428-6a37-4fcf-8803-972c34b49a61.json
data/live/reconciliation/latest.json
site/status.json
```

The generated `data/live/`, `data/workflows/`, and `logs/` files are local
operational artifacts and should remain uncommitted. The dashboard status file
is sanitized and may be reviewed for commit separately.

## Result

The launchd-localized environment can run the wrapper manually and publish a
healthy Alpaca paper dashboard status. Launchd remains disabled and unloaded.

The next step should review whether to load launchd in disabled mode, or defer
automation until an actionable paper buy/sell day has been observed manually.
