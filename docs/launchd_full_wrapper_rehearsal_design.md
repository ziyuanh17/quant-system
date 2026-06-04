# Launchd Full Wrapper Rehearsal Design

This design describes the first non-preflight launchd-triggered Alpaca paper
wrapper run from the runtime clone.

It is still not real-money trading. It is one controlled launchd-triggered run
of the existing Alpaca paper wrapper, followed by immediate unload and review.

## Goal

Prove that launchd can run the full wrapper from:

```text
/Users/ziyuan/Code/quant-system-runtime
```

The full wrapper should:

```text
load .env
refresh provider market data
validate normalized market bars
generate the latest strategy signal
submit to Alpaca paper only if the signal is actionable
write live audit artifacts
reconcile local artifacts against Alpaca paper state
optionally publish sanitized dashboard status
write a workflow record
```

## Non-Goals

This rehearsal must not:

- use the Codex workspace under `Documents` as the launchd runtime path
- enable real-money trading
- leave launchd loaded after inspection
- rely on the calendar trigger firing naturally
- run more than one explicit `launchctl kickstart`
- retry broker submission automatically
- commit local runtime artifacts, `.env`, `.venv`, logs, or local plists

## Runtime Readiness Checklist

Before installing the temporary launchd plist, verify:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
git status --short --ignored
git remote -v
head -n 3 .venv/bin/quant
plutil -lint configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist
```

Expected:

- Git remote points to `git@github.com:ziyuanh17/quant-system.git`
- only ignored runtime files appear: `.env`, `.venv/`, `logs/`, local plist
- `.venv/bin/quant` points to `/Users/ziyuan/Code/quant-system-runtime`
- the local launchd plist points only to `/Users/ziyuan/Code/quant-system-runtime`

If the main repo has new reviewed commits, update the runtime clone first:

```bash
cd /Users/ziyuan/Code/quant-system-runtime
git pull origin main
```

If dependencies changed, refresh the runtime virtualenv:

```bash
.venv/bin/python -m pip install -e ".[broker-alpaca]"
```

## Safety Preconditions

Before the non-preflight `kickstart`, verify `.env` in the runtime clone is
still paper-only:

```text
QUANT_BROKER=alpaca-paper
QUANT_ALPACA_PAPER_API_KEY=...
QUANT_ALPACA_PAPER_SECRET_KEY=...
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_MAX_ORDER_NOTIONAL=...
```

The safety variables are named "live" because the adapter boundary is shaped
like live trading, but this specific wrapper must still use the explicit
Alpaca paper command and paper credentials.

Stop if:

- `QUANT_BROKER` is not `alpaca-paper`
- any live-account Alpaca credential is present in the wrapper path
- `QUANT_MAX_ORDER_NOTIONAL` is missing
- the runtime clone has unexpected tracked changes
- an old launchd job is already loaded
- an installed launchd plist already exists and has not been reviewed

## Artifact Baseline

Before the run, capture counts and latest files for:

```text
logs/alpaca-paper-refresh-*.log
data/live/orders/
data/live/fills/
data/live/account_snapshots/
data/live/reconciliation/
data/workflows/alpaca-paper-refresh/
site/status.json
```

The runtime clone may have fewer existing artifacts than the Codex workspace.
That is acceptable. The point is to know exactly what the launchd run creates.

## Launchd Run Sequence

Install a temporary plist from the runtime clone:

```bash
cp \
  /Users/ziyuan/Code/quant-system-runtime/configs/launchd/com.quant-system.alpaca-paper-refresh.local.plist \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Make only the installed copy loadable:

```bash
/usr/libexec/PlistBuddy -c 'Set :Disabled false' \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

For this full-wrapper rehearsal, do not add:

```text
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true
```

Validate and bootstrap:

```bash
plutil -lint ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist

launchctl bootstrap gui/$(id -u) \
  ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Inspect before triggering:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
launchctl blame gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Expected before trigger:

```text
state = not running
runs = 0
last exit code = (never exited)
```

Trigger exactly once:

```bash
launchctl kickstart \
  gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Inspect after trigger:

```bash
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
```

Expected after trigger:

```text
runs = 1
last exit code = 0
```

Unload and remove the installed plist immediately after inspection:

```bash
launchctl bootout gui/$(id -u)/com.quant-system.alpaca-paper-refresh
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

## Expected Artifacts

At minimum, expect:

```text
logs/alpaca-paper-refresh-*.log
data/workflows/alpaca-paper-refresh/*.json
data/live/account_snapshots/*.json
data/live/reconciliation/latest.json
```

Depending on the strategy signal, the run may also create:

```text
data/live/orders/*.json
data/live/fills/*.json
```

An order artifact is acceptable only if the workflow record says the latest
signal was actionable and the notional stayed within `QUANT_MAX_ORDER_NOTIONAL`.
If an order is submitted, reconcile immediately and check the Alpaca paper
dashboard for unexpected open orders.

## Review Checklist

Review the latest wrapper log:

```text
preflight_only=false
completed_at=...
```

Review the latest workflow record:

```text
status
message
latest_signal
broker_submission_attempted
broker_submission_skipped_reason
```

Review reconciliation:

```text
data/live/reconciliation/latest.json
```

Expected reconciliation result:

```text
status = passed
differences = 0
```

Review launchd cleanup:

```text
launchctl print gui/$(id -u)/com.quant-system.alpaca-paper-refresh
ls ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Expected cleanup:

```text
service not found
installed plist not found
```

## Stop Conditions

Stop and diagnose before any retry if:

- launchd exits nonzero
- the wrapper log is missing
- `preflight_only=true` appears unexpectedly
- workflow status is not `succeeded`
- reconciliation is not `passed`
- a broker order appears without a matching local order artifact
- order notional exceeds `QUANT_MAX_ORDER_NOTIONAL`
- launchd remains loaded after cleanup

## Outcome Criteria

This rehearsal passes only if:

- launchd reports `runs = 1`
- launchd reports `last exit code = 0`
- the wrapper log records `preflight_only=false`
- workflow and reconciliation artifacts are written
- reconciliation passes
- the launchd job is unloaded and the installed plist is removed
- any broker submission is explainable from the workflow record and visible in
  Alpaca paper only

After this design is reviewed, the next milestone can execute exactly one full
launchd-triggered wrapper rehearsal from the runtime clone.

## Follow-Up Result

The first full launchd-triggered wrapper rehearsal succeeded from the runtime
clone. It exited with code `0`, wrote a workflow record, produced an Alpaca
paper account snapshot, passed reconciliation, and skipped broker submission
because the latest signal was `hold`.

See [launchd_full_wrapper_rehearsal.md](launchd_full_wrapper_rehearsal.md).
