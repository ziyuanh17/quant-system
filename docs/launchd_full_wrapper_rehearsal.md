# Launchd Full Wrapper Rehearsal

This note records the first non-preflight launchd-triggered Alpaca paper
wrapper run from the runtime clone.

## Context

- Date: 2026-06-03, America/Los_Angeles
- Runtime clone: `/Users/ziyuan/Code/quant-system-runtime`
- Label: `com.quant-system.alpaca-paper-refresh`
- Installed rehearsal plist:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- Installed copy `Disabled`: `false`
- `QUANT_ALPACA_PAPER_PREFLIGHT_ONLY`: not set in the installed plist
- `launchctl bootstrap` attempted: yes
- `launchctl kickstart` attempted: yes, exactly once
- Full Alpaca paper workflow reached: yes
- Real-money trading path reached: no

## Preconditions Checked

The runtime clone was used instead of the Codex workspace under `Documents`:

```text
/Users/ziyuan/Code/quant-system-runtime
```

Readiness checks showed:

```text
origin = git@github.com:ziyuanh17/quant-system.git
.venv/bin/quant -> /Users/ziyuan/Code/quant-system-runtime/.venv/bin/python
launchd local plist -> /Users/ziyuan/Code/quant-system-runtime
```

The runtime `.env` safety check showed:

```text
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_MAX_ORDER_NOTIONAL=400
QUANT_BROKER=alpaca-paper
QUANT_ALPACA_PAPER_API_KEY=<set>
QUANT_ALPACA_PAPER_SECRET_KEY=<set>
```

No launchd service was loaded and no installed launchd plist existed before
the rehearsal.

## Artifact Baseline

Before the full run, the runtime clone had two wrapper logs from prior
preflight checks:

```text
logs/alpaca-paper-refresh-20260604T052342Z.log
logs/alpaca-paper-refresh-20260604T053107Z.log
```

The runtime clone did not yet have Alpaca paper workflow artifacts under:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/workflows/alpaca-paper-refresh
```

## Launchd Run

The installed plist was copied from the runtime clone and changed to
`Disabled=false`. No preflight-only environment override was added.

Pre-kickstart launchd state:

```text
state = not running
runs = 0
last exit code = (never exited)
```

After one `launchctl kickstart`, launchd reported:

```text
state = not running
runs = 1
last exit code = 0
```

The wrapper log was:

```text
logs/alpaca-paper-refresh-20260604T054840Z.log
```

Key log lines:

```text
preflight_only=false
Workflow: alpaca-paper-refresh
Status: succeeded
Message: data refreshed and Alpaca paper workflow completed
Latest signal: hold
Broker submission attempted: False
Broker submission skipped reason: latest strategy signal is hold
Record: data/workflows/alpaca-paper-refresh/7f450d81-9223-465c-88f8-19d41412d368.json
completed_at=2026-06-04T05:48:49Z
```

## Workflow Outcome

The workflow record reported:

```text
workflow_id = 7f450d81-9223-465c-88f8-19d41412d368
status = succeeded
latest_signal_action = hold
latest_signal_reason = latest strategy signal is hold
broker_submission_attempted = false
broker_submission_skipped_reason = latest strategy signal is hold
order_artifact_paths = []
fill_artifact_paths = []
```

Generated artifacts:

```text
data/raw/provider=yfinance/modality=market_bars/symbol=AAPL/start=2024-01-01_end=latest.csv
data/normalized/market_bars/AAPL.csv
data/validation/market_bars/AAPL.json
data/metadata/market_bars/AAPL.json
data/live/account_snapshots/dda11657-52e0-4b57-9bfb-bb103be3e410.json
data/live/reconciliation/latest.json
data/workflows/alpaca-paper-refresh/7f450d81-9223-465c-88f8-19d41412d368.json
```

No order or fill artifacts were created.

## Reconciliation

The reconciliation report showed:

```text
status = passed
difference_count = 0
```

The account snapshot included zero positions and a present `buying_power`
field. Sensitive account values were not copied into this note.

## Cleanup

After inspection, the launchd job was unloaded:

```bash
launchctl bootout gui/501/com.quant-system.alpaca-paper-refresh
```

The temporary installed plist was removed:

```bash
rm ~/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist
```

Follow-up checks confirmed:

```text
launchctl print -> service not found
installed plist -> file not found
```

## Outcome

The first non-preflight launchd-triggered Alpaca paper wrapper run succeeded
from the runtime clone. It refreshed data, validated market bars, generated a
hold signal, wrote an account snapshot, reconciled successfully, and wrote a
workflow record.

Because the latest signal was `hold`, no broker submission was attempted and no
paper order was created.

The next step should design how and when to leave the launchd schedule loaded
for recurring Alpaca paper runs, including monitoring and rollback rules.
