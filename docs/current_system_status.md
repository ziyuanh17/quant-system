# Current System Status

This is the canonical current-state summary for the repository. It describes
checked-in source capabilities, not the current contents of a broker account,
runtime clone, or loaded service. Those operational facts must be verified
separately from fresh read-only evidence.

## Source Baseline

- Branch: `main`
- Reviewed source commit before this uncommitted reconciliation-failure bundle:
  `cacf25a`
- Repository: `https://github.com/ziyuanh17/quant-system`
- Development workspace: `/Users/mochifufu/Code/quant-system`
- Runtime clone: `/Users/mochifufu/Code/quant-system-runtime`

The runtime clone is a separate operational deployment. Do not assume it is at
the source baseline above without auditing it.

## Implemented Architecture

The repository currently contains two execution families.

### Legacy Signal Workflows

The original CLI and scheduled workflows remain supported:

```text
strategy signal
  -> order-oriented risk checks
  -> local paper, dry-run, or Alpaca paper workflow
  -> operational artifacts and reconciliation
```

These include the finite local paper and dry-run schedulers, data-refresh
workflows, the safety-gated Alpaca paper CLI/workflow, launchd wrapper, health
checks, dashboard publishing, and the read-only web console.

### Semantic Target Foundation

The newer architecture makes desired exposure durable before deriving orders:

```text
strategy evaluation
  -> immutable strategy target
  -> contributor-set portfolio aggregation
  -> immutable risk target
  -> atomic execution-plan claim
  -> append-only execution lifecycle
  -> broker state and reconciliation
```

Checked-in semantic-target capabilities include:

- native target strategies and VectorBT target-amount backtests;
- legacy-simulation equivalence evidence;
- immutable strategy, portfolio, risk, and evaluation artifacts;
- deterministic multi-strategy aggregation with stale/unavailable blocking;
- whole-share operational validation without silent rounding;
- restart-safe execution plans and append-only lifecycle events;
- durable blocked and ambiguous outcomes;
- reconciliation-confirmed satisfaction and detect-only drift;
- opt-in semantic dry-run evaluation;
- opt-in durable local semantic-paper execution;
- controlled API-only orchestration that durably composes strategy,
  portfolio, risk, and dry-run/local-paper stages;
- deterministic no-network orchestration rehearsal with immutable,
  evidence-verified scenario reports;
- explicit local reconciliation-failure injection proving a fill cannot become
  satisfied when account-wide reconciliation fails;
- immutable, time-bounded semantic-target activation authorizations and
  durable evaluation artifacts that bind the exact verified local rehearsal
  report;
- API-only activated dry-run and local semantic-paper wrappers with atomic
  one-evaluation-to-one-orchestration consumption claims;
- second-layer no-network activation-consumption rehearsal with immutable,
  evidence-verified allowed, blocked, restart, and single-consumption results;
- reviewed-request activated dry-run CLI with no mode, broker, paper, Alpaca,
  scheduler, runtime, or order-submission capability;
- read-only activated dry-run request inspection that explains current
  validity and intended orders without writing or consuming evidence;
- opt-in Alpaca semantic-target paper API integration with explicit activation,
  final operational risk checks, and recovery by deterministic client order ID.

All semantic-target orchestration and Alpaca paths are API capabilities only.
They are not exposed by the CLI, recurring scheduler, launchd wrapper, or
runtime service.

Activation gate v1 can evaluate authorization only for semantic dry-run and
local semantic paper. It explicitly blocks Alpaca paper scope and does not
itself invoke an authorized workflow. Activation artifacts are written under
the caller-selected root in `authorizations/` and `evaluations/`.

The separate activated wrappers revalidate and consume gate evidence before
calling controlled dry-run or local semantic paper. Blocked activation creates
no strategy, portfolio, risk, lifecycle, or semantic-paper artifacts. These
wrappers are not exposed operationally.

The activation-consumption rehearsal is separate from the base orchestration
rehearsal to avoid circular authorization evidence. It binds the completed base
report by path and digest and remains API-only.

The semantic-target operator commands are limited to
`quant dry-run inspect-activated-target`, which only reads and explains a
request, and `quant dry-run activated-target`, which consumes a
schema-versioned reviewed request and hardcodes the activated dry-run path.
Neither command can select semantic local paper or Alpaca; those paths remain
API-only.

On June 14, 2026, the command passed one local synthetic operator rehearsal.
Running the same request twice produced one durable `would_submit` observation
for an intended `BUY 2 AAPL` order and created no paper, order, or fill
directories in the operator output. See
[activated_dry_run_operator_rehearsal.md](activated_dry_run_operator_rehearsal.md).

## Safety And Activation Boundary

- No source capability implies permission to submit an order.
- Broker-connected order submission requires the relevant safety gates and
  explicit human approval immediately before an order-capable operation.
- Semantic-target Alpaca submission additionally requires
  `alpaca_submission_enabled=True`.
- Working orders block semantic-target execution.
- Fractional shares are allowed in research but rejected by current
  operational target validation without rounding.
- Drift policy is detect-only; the system does not automatically repair a
  diverged broker position.
- Real-money trading is not implemented.
- Recurring Alpaca paper scheduler state must be checked directly before any
  operational work. Historical documents do not establish current scheduler
  state.

## Operational Truth

The last documented controlled rehearsal on June 11, 2026 observed
`AAPL=-1`, `F=+1`, zero open orders, and passing reconciliation. That is a
historical observation, not current broker truth.

Neither AAPL nor F is globally protected by the current design. Any future
automation may touch a position only when its approved target, risk policy,
execution lifecycle, and explicit operational authorization allow it.

## Current Review Boundary

The semantic-target contracts and Alpaca API integration are checked in.
Before connecting semantic targets to recurring operations:

1. review the checked-in lifecycle and Alpaca integration as one safety
   boundary;
2. review the controlled orchestration and reconciliation-failure rehearsal
   evidence;
3. review the activated dry-run operator boundary;
4. separately review any CLI, runtime-clone, or recurring scheduler exposure;
5. obtain explicit approval before every broker order-capable rehearsal.

## Documentation Rules

- [architecture.md](architecture.md) and
  [semantic_target_architecture.md](semantic_target_architecture.md) describe
  current source architecture.
- [runbook.md](runbook.md) describes supported operator commands.
- [codex_project_handoff.md](codex_project_handoff.md) gives collaboration and
  safety context.
- [roadmap.md](roadmap.md) is a historical milestone ledger plus current
  recommendation.
- Incident, rehearsal, migration, and activation documents preserve evidence
  from the date stated in each file. Their commands and observations must not
  be treated as current authorization or current broker/runtime truth.
