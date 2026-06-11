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
- GitHub source commit used for Studio bootstrap: `3f60b4f`
- Repository: `https://github.com/ziyuanh17/quant-system`
- Both Studio clones were created from GitHub at the same commit.
- Studio development and runtime clones each passed `make check` with
  212 tests.

The MacBook Air and Studio development clone may contain uncommitted
documentation updates from the migration review. Inspect Git status before
making further changes.

## Current Broker State

As of the June 10, 2026 Studio read-only verification:

```text
broker=alpaca-paper
cash=100290.73
buying_power=399643.06
positions=AAPL:-1
open_orders=0
reconciliation=passed
reconciliation_differences=0
```

The retained AAPL short is intentional and must remain exactly `-1` during the
controlled rehearsal.

## Current Operational Boundary

- Both Air and Studio launchd jobs are unloaded.
- The Studio-local plist is valid and still has `Disabled=true`.
- The Studio passed a preflight-only wrapper run.
- No order was submitted during migration.
- The next order-capable action is milestone 87: the dedicated controlled
  Alpaca paper rehearsal.

The provisional rehearsal candidate is `F`. After the regular market opens,
refresh account truth, open orders, asset metadata, and the current price.
Then request immediate explicit approval containing:

```text
symbol=F
reference price=<fresh current price>
maximum order notional=400
protected position=AAPL=-1
```

Do not reuse the prior closed-market `$14.30` reference price without
refreshing it.

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

1. Review the Studio-controlled order rehearsal after market open.
2. Execute it only after immediate explicit approval.
3. Review resulting positions, artifacts, reconciliation, and dashboard.
4. Decide separately whether to load the Studio launchd schedule.
5. Observe the first natural Studio scheduled run before closing migration.
6. Configure Studio GitHub push authentication before development pushes.
