# Codex Project Handoff

This document gives a new Codex thread the durable context needed to continue
development and operations safely. Read
[current_system_status.md](current_system_status.md) first for the canonical
checked-in capability summary.

## Collaboration Rules

- Do not commit or push changes unless the user explicitly requests it.
- After checking Git status, keep roadmap statuses consistent:
  committed work is `Done`, uncommitted review bundles are `In Review`, and
  work not started is `Planned` or `Next`.
- Annotate non-obvious code sufficiently for later debugging.
- Give every Python module and package a concise module-level docstring that
  explains its purpose; Ruff enforces this with `D100` and `D104`.
- Never revert unrelated user changes.
- Never submit an Alpaca paper order without explicit approval immediately
  before the exact order-capable command.
- Treat broker positions as current truth only after fresh read-only
  verification. No symbol is globally protected from an approved strategy
  target, but no position may be changed without the applicable safety and
  authorization gates.

## Host Responsibilities

```text
Mac Studio development clone:
  /Users/mochifufu/Code/quant-system
  coding, tests, documentation, and Codex work

Mac Studio runtime clone:
  /Users/mochifufu/Code/quant-system-runtime
  credentials, operational artifacts, rehearsals, and deployed services

MacBook Air:
  remote-control and fallback development host
  no recurring scheduler
```

Do not run development experiments from the Studio runtime clone. Promote
reviewed source changes through GitHub before updating the runtime clone.

## Current Source State

- Git branch: `main`
- Current reviewed GitHub source commit before the uncommitted semantic-target
  reconciliation-failure bundle: `cacf25a`
- Repository: `https://github.com/ziyuanh17/quant-system`
- The runtime clone version is not established by this source document. Audit
  it before operational work.
- The source includes the legacy signal workflows and the checked-in semantic
  target foundation through the opt-in Alpaca paper API integration.
- Semantic-target Alpaca execution is not connected to a CLI, scheduler,
  launchd wrapper, or runtime service.

The MacBook Air and Studio development clone may contain uncommitted
documentation updates from the migration review. Inspect Git status before
making further changes.

## Last Documented Broker Observation

The June 11, 2026 controlled Studio rehearsal observed:

```text
broker=alpaca-paper
positions=AAPL:-1,F:+1
open_orders=0
reconciliation=passed
reconciliation_differences=0
```

This is historical evidence, not current broker state. Before relying on or
changing either position, perform a fresh read-only snapshot and
reconciliation. AAPL and F are not globally protected positions.

## Current Operational Boundary

- Do not infer launchd state from historical rehearsal documents. Check it
  directly before operational work.
- The read-only web console is independent from trading scheduler activation.
- Existing legacy Alpaca paper CLI/workflow commands remain order-capable.
- The semantic-target Alpaca integration is API-only and requires explicit
  activation plus the live-shaped Alpaca paper safety configuration.
- Real-money execution is not implemented.

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

An unloaded job reports `service not found`; any other result must be reviewed
before proceeding.

## Recommended Next Work

1. Keep semantic-target activation separate from the legacy scheduled signal
   lane.
2. Build a controlled orchestration boundary for semantic dry-run or local
   semantic paper before exposing Alpaca semantic targets operationally.
3. Rehearse stale decisions, working orders, restart recovery, durable blocked
   events, and failed reconciliation.
4. Review the API-only operational activation gate, which currently supports
   dry-run and local semantic paper and explicitly blocks Alpaca paper.
5. Review the activated local orchestration wrappers and their atomic
   one-evaluation-to-one-orchestration consumption claim.
6. Review the second-layer activation-consumption rehearsal evidence before
   proposing any operator exposure.
7. Review the activated dry-run CLI boundary; it is the only semantic-target
   operator command and cannot select paper or Alpaca.
8. Review the bounded autonomous dry-run API and rehearse its repeated-run,
   restart, expiry, limit, and halt-on-block behavior before proposing a
   scheduler connection.
9. Review the finite manually started autonomous dry-run loop before any
   recurring scheduler proposal.
10. Review any proposed paper, Alpaca, runtime-clone, or scheduler exposure
   separately.
11. Require explicit approval immediately before any broker order-capable
   command or rehearsal.
