# Alpaca Paper Schedule Design

This note defines the first recurring Alpaca paper schedule policy. It is a
design checkpoint only: do not install a cron, launchd, or systemd schedule
until this policy has been reviewed.

## Goal

Run the Alpaca paper workflow often enough to prove server-style operation, but
not so often that the system creates noisy artifacts or paper orders before the
order lifecycle is more mature.

The first recurring setup should prove:

- the wrapper starts from the intended working directory
- `.env` is loaded by the wrapper, not by an interactive shell assumption
- yfinance data refresh and validation still work on schedule
- the latest strategy decision is visible in the workflow record
- Alpaca paper account snapshot and reconciliation still pass
- `site/status.json` is refreshed after each run
- the lock prevents overlapping executions

## Recommended First Schedule

- Runner: local cron or launchd on the machine that already has the repo,
  `.env`, Python environment, and SSH/GitHub setup
- Frequency: once per market weekday
- Time: near the end of the regular US market session
- Suggested local time: 12:55 PM America/Los_Angeles
- Wrapper: `scripts/run_alpaca_paper_refresh.sh`
- Quantity: 1 share
- Dashboard publishing: enabled
- Paper service lane: disabled in dashboard publishing unless the older local
  paper scheduler/signal lane is actively maintained again

This means the first schedule should behave like a daily operational rehearsal,
not an intraday trading bot.

## Pre-Enable Checklist

Before enabling any recurring schedule:

1. Run wrapper preflight:

   ```bash
   QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh
   ```

2. Run one manual full wrapper cycle:

   ```bash
   bash scripts/run_alpaca_paper_refresh.sh
   ```

3. Publish Alpaca-only dashboard status:

   ```bash
   quant ops publish-status \
     --no-check-paper-service \
     --no-check-comparison \
     --check-alpaca-paper
   ```

4. Review:

   ```text
   logs/alpaca-paper-refresh-*.log
   data/workflows/alpaca-paper-refresh/
   data/live/reconciliation/latest.json
   site/status.json
   ```

5. Confirm:

   - `alpaca_paper_workflow_status` is `succeeded`
   - `alpaca_paper_reconciliation_status` is `passed`
   - `alpaca_paper_reconciliation_difference_count` is `0`
   - latest signal action and broker submission outcome are populated
   - no unexpected open paper order exists in Alpaca
   - order quantity and `QUANT_MAX_ORDER_NOTIONAL` are still intentionally tiny

## Cron Draft

Use an absolute path and keep the schedule commented out until review:

```cron
# 55 12 * * 1-5 cd /absolute/path/to/quant-system && bash scripts/run_alpaca_paper_refresh.sh
```

Cron uses the machine's local timezone. On the current development machine, the
intended timezone is America/Los_Angeles.

## launchd Draft

For macOS, prefer launchd over cron when the process should run only while the
machine is available under the user account.

The checked-in template is:

```text
configs/launchd/com.quant-system.alpaca-paper-refresh.plist.example
```

It starts as a review-only template with `Disabled=true` and
`/absolute/path/to/quant-system` placeholders. Copy it to a local plist, replace
every placeholder with the actual repo path, run preflight, and review the
dashboard. Before loading it with launchd, change `Disabled` to `false`; launchd
cannot bootstrap the job while it remains `true`.
Follow [launchd_localization.md](launchd_localization.md) for the exact local
copy, validation, load, and unload commands.
Follow
[launchd_recurring_schedule_activation_design.md](launchd_recurring_schedule_activation_design.md)
before leaving the job loaded for unattended recurring runs.

Draft policy:

```text
ProgramArguments:
  /bin/bash
  scripts/run_alpaca_paper_refresh.sh
WorkingDirectory:
  /absolute/path/to/quant-system
StartCalendarInterval:
  Weekday: 1-5
  Hour: 12
  Minute: 55
```

Do not install this until the exact absolute repo path and environment behavior
have been checked with preflight.

## Wrapper Environment

Recommended `.env` settings for the first recurring Alpaca paper run:

```bash
QUANT_LIVE_TRADING_ENABLED=true
QUANT_LIVE_TRADING_CONFIRMATION=I_UNDERSTAND_LIVE_TRADING_RISK
QUANT_BROKER=alpaca-paper
QUANT_QUANTITY=1
QUANT_MAX_ORDER_NOTIONAL=400
QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=true
QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH=site/status.json
QUANT_ALPACA_PAPER_PUBLISH_STATUS_FAIL_ON_FAILED=false
```

The exact `QUANT_MAX_ORDER_NOTIONAL` should be reviewed against the intended
symbol before enabling the schedule. It should be high enough for one intended
paper share and low enough to block accidental larger sizing.

## Dashboard Publishing Mode

When the older local paper scheduler/signal lane is inactive, publish status
with:

```bash
quant ops publish-status \
  --no-check-paper-service \
  --no-check-comparison \
  --check-alpaca-paper
```

This keeps the dashboard focused on the active Alpaca paper lane instead of
showing warnings for intentionally inactive local paper artifacts.

## Non-Goals

This schedule design does not:

- enable the schedule
- run every few minutes
- add real-money trading
- increase order size
- retry broker submissions automatically
- place orders outside Alpaca paper
- solve market-holiday detection
- guarantee fills
- replace manual dashboard and broker-account review

## Open Improvements

Before moving beyond daily paper rehearsals, consider:

- market calendar awareness for holidays and early closes
- explicit max daily order count
- broker-side open-order refresh before each run
- clearer stale-status handling on the dashboard
- scheduled GitHub Pages publishing after status generation
- paper-run review notes for actionable buy/sell days
