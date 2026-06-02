# Launchd Local Preflight

This note records the first local launchd preflight for the Alpaca paper
wrapper. It did not load, enable, or kickstart launchd.

## Summary

- Date: 2026-06-01, America/Los_Angeles
- Template: `configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example`
- Local copy: `configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist`
- Local copy tracked by git: no
- `plutil` validation: passed
- launchd `Disabled`: `true`
- Working directory: `/Users/ziyuan/Documents/Codex/2026-05-07/quant-system`
- Schedule: Monday-Friday at 12:55 local time
- launchd load attempted: no
- launchd enable attempted: no
- launchd kickstart attempted: no
- Wrapper preflight: passed

## Preflight Output

The wrapper was run in preflight mode:

```bash
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh
```

Observed:

```text
preflight_only=true
preflight completed without broker submission
```

The preflight resolved the expected Alpaca paper wrapper paths:

```text
workflow_output_dir=data/workflows/alpaca-paper-refresh
order_output_dir=data/live/orders
reconciliation_output_path=data/live/reconciliation/latest.json
lock_path=data/locks/alpaca-paper-refresh.lock
```

## Result

The local launchd plist is ready for human review, but it remains disabled and
unloaded. The next step should be a manual full wrapper run and dashboard review
before any launchd load or enable action.
