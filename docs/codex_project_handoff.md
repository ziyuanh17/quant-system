# Codex Project Handoff

This document gives a new Codex thread the durable context needed to continue
development and operations safely after the Mac Studio migration.

## Collaboration Rules

- Do not commit or push changes unless the user explicitly requests it.
- After checking Git status, keep roadmap statuses consistent:
  committed work is `Done`, uncommitted review bundles are `In Review`, and
  work not started is `Planned` or `Next`.
- Annotate non-obvious code sufficiently for later debugging.
- Never revert unrelated user changes.
- Never submit an Alpaca paper order without explicit approval immediately
  before the exact order-capable command.
- Do not automatically recover or close the intentionally retained
  one-share AAPL paper short.

## Host Responsibilities

```text
Mac Studio development clone:
  /Users/mochifufu/Code/quant-system
  coding, tests, documentation, and Codex work

Mac Studio runtime clone:
  /Users/mochifufu/Code/quant-system-runtime
  credentials, operational artifacts, rehearsals, and future launchd service

MacBook Air:
  remote-control and fallback development host
  no recurring scheduler
```

Do not run development experiments from the Studio runtime clone. Promote
reviewed source changes through GitHub before updating the runtime clone.

## Current Source State

- Git branch: `main`
- Current reviewed GitHub source commit: `4853789`
- Repository: `https://github.com/ziyuanh17/quant-system`
- The Studio runtime clone is at `4853789`, matching `origin/main`.
- The market-hours reconciliation remediation passed focused runtime tests and
  a live read-only reconciliation before the controlled rehearsal.

The MacBook Air and Studio development clone may contain uncommitted
documentation updates from the migration review. Inspect Git status before
making further changes.

## Current Broker State

As of the June 11, 2026 controlled Studio rehearsal review:

```text
broker=alpaca-paper
positions=AAPL:-1,F:+1
open_orders=0
reconciliation=passed
reconciliation_differences=0
```

The retained AAPL short is intentional and remains exactly `-1`. The new
one-share F long is the expected result of the successful controlled
rehearsal. Do not close either position automatically.

## Current Operational Boundary

- Both Air and Studio launchd jobs are unloaded.
- The Studio-local plist is valid and still has `Disabled=true`.
- The Studio passed a preflight-only wrapper run.
- Milestone 87 passed: the approved one-share F paper buy filled at an average
  price of `$14.33`, AAPL remained `-1`, and reconciliation passed with zero
  differences.
- No cleanup order was submitted.
- The next operational decision is whether to activate the Studio recurring
  launchd schedule. Activation requires separate explicit approval.

## Verification Commands

Studio development verification:

```bash
cd /Users/mochifufu/Code/quant-system
make check
```

Studio runtime audit and no-order preflight:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
bash scripts/migration/audit_host.sh "$PWD"
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true \
  bash scripts/run_alpaca_paper_refresh.sh
```

Studio read-only broker verification:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
set -a
source .env
set +a
.venv/bin/quant live alpaca-paper-snapshot --from-env
.venv/bin/quant live alpaca-paper-reconcile --from-env
```

Confirm the scheduler remains unloaded:

```bash
launchctl print \
  "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
```

The expected result before scheduler cutover is `service not found`.

## Remaining Migration Work

1. Review and commit the successful rehearsal evidence and scheduler
   activation readiness record.
2. Promote that reviewed documentation to the runtime clone.
3. Decide separately whether to load the Studio launchd schedule.
4. Observe the first natural Studio scheduled run before closing migration.
5. Decide separately whether the expected `F=+1` rehearsal position should
   remain or be closed.
