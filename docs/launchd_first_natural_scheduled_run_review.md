# Launchd First Natural Scheduled Run Review

This note records the first launchd-triggered Alpaca paper run that happened
from the recurring calendar schedule, without manual `kickstart`.

## Installed Job

- Label: `com.quant-system.alpaca-paper-refresh`
- Installed plist:
  `/Users/ziyuan/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist`
- Runtime clone:
  `/Users/ziyuan/Code/quant-system-runtime`
- Wrapper:
  `/Users/ziyuan/Code/quant-system-runtime/scripts/run_alpaca_paper_refresh.sh`
- Schedule: weekdays at 12:55 PM local time

## Launchd State

Inspection on June 4, 2026 showed:

```text
state = not running
runs = 1
last exit code = 0
```

That confirms launchd naturally triggered the job and the process exited
successfully.

## Runtime Artifacts

The natural run produced:

```text
logs/alpaca-paper-refresh-20260604T200614Z.log
data/workflows/alpaca-paper-refresh/45d8388c-2021-4562-9077-a3d335f121f5.json
data/live/account_snapshots/25be56b2-b791-45ff-9f70-04d684dee174.json
data/live/reconciliation/latest.json
site/status.json
```

The wrapper ran with:

```text
publish_status_after_run=true
preflight_only=false
symbol=AAPL
provider=yfinance
start=2024-01-01
```

## Workflow Outcome

The Alpaca paper workflow record reported:

```text
status=succeeded
latest_signal_action=hold
broker_submission_attempted=false
broker_submission_skipped_reason=latest strategy signal is hold
```

No Alpaca paper order was submitted because the strategy signal was `hold`.

## Reconciliation Outcome

The reconciliation report passed:

```text
status=passed
local_order_count=0
broker_order_count=0
local_fill_count=0
broker_fill_count=0
local_position_count=0
broker_position_count=0
differences=[]
```

This is the expected state for a hold signal with no paper order submission.

## Dashboard Outcome

The dashboard status file was refreshed, but it reported:

```text
status=failed
issue_count=4
```

The Alpaca paper lane itself was healthy:

```text
alpaca_paper_workflow_status=succeeded
alpaca_paper_reconciliation_status=passed
alpaca_paper_reconciliation_difference_count=0
```

The failed dashboard status came from older inactive lanes:

```text
missing_scheduler_run
missing_paper_signal
missing_paper_state
missing_comparison_report
```

These checks are useful when the local paper/dry-run lanes are intentionally
active, but they make the current scheduled Alpaca paper workflow look failed
even though the active broker-connected paper lane passed.

## Decision

Keep the recurring launchd schedule loaded. The first natural run proved:

- launchd can trigger the runtime clone on its own calendar schedule,
- the wrapper reaches the full Alpaca paper workflow,
- data refresh and validation complete,
- broker submission is skipped correctly for a hold signal,
- Alpaca paper account snapshot and reconciliation work,
- stderr is empty.

The next fix should align dashboard health scope so the status page reflects
the active Alpaca paper workflow instead of stale inactive paper/dry-run lanes.
