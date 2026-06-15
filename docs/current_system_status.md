# Current System Status

This is the canonical current-state summary for the repository. It describes
checked-in source capabilities, not the current contents of a broker account,
runtime clone, or loaded service. Those operational facts must be verified
separately from fresh read-only evidence.

## Source Baseline

- Branch: `main`
- Reviewed source commit before this uncommitted supervised-provider operator
  bundle: `3d64ae3`
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
- API-only bounded autonomous dry-run authorization with exact deployment
  limits, atomic run claims, durable run outcomes, and halt-on-block behavior;
- evidence-verified no-network autonomous dry-run rehearsal covering repeated
  runs, restart safety, expiry, target limits, and halt-after-block behavior;
- finite manually started autonomous dry-run CLI that accepts one
  content-bound request manifest, stops on block, and cannot run indefinitely;
- bounded API-only supervised autonomous dry-run service with fresh requests,
  per-cycle health and shutdown checks, append-only cycle events, and restart
  continuation;
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

The autonomous dry-run runner is also API-only. It permits repeated routine
dry-runs under one bounded deployment authorization, but it has no scheduler
or broker connection. See
[autonomous_dry_run_authorization.md](autonomous_dry_run_authorization.md).

On June 15, 2026, its complete no-network rehearsal passed repeated-run,
restart, expiry, target-limit, and halt-after-block scenarios. It produced no
order files, fill files, or semantic-paper directories. See
[autonomous_dry_run_rehearsal.md](autonomous_dry_run_rehearsal.md).

The autonomous operator command is limited to
`quant dry-run autonomous-finite-loop`. It processes only the exact
content-hashed request list in one manifest and has no recurring scheduler,
paper, Alpaca, broker, or runtime-service connection.

On June 15, 2026, the actual finite-loop command passed exact-list and restart
rehearsals for two successful requests, then separately proved that a
working-order block stopped before the second request. Both rehearsals produced
zero order and fill files. See
[finite_autonomous_dry_run_loop_rehearsal.md](finite_autonomous_dry_run_loop_rehearsal.md).

The supervised autonomous dry-run service is API-only in the checked-in
baseline. It checks health and an explicit shutdown signal before every cycle,
stops on any degraded or blocked condition, and uses append-only cycle events
for restart continuation. It is not connected to CLI, launchd, runtime
deployment, paper, Alpaca, a broker, or a recurring scheduler. See
[supervised_autonomous_dry_run_service.md](supervised_autonomous_dry_run_service.md).

On June 15, 2026, its evidence-verified no-network rehearsal passed eight
scenarios and produced 10 cycle events, 8 health checks, 5 autonomous dry-run
records, and zero order, fill, semantic-paper, or Alpaca directories. See
[supervised_autonomous_dry_run_rehearsal.md](supervised_autonomous_dry_run_rehearsal.md).

The checked-in provider-contract baseline includes immutable,
production-shaped health snapshots and request envelopes. Versioned policy
validation fails closed on missing, stale, expired, future-dated, wrong-source,
wrong-cycle, or unauthorized inputs. These adapters remain API-only and have
no deployment or operational connection. See
[supervised_provider_contracts.md](supervised_provider_contracts.md).

The checked-in local provider assembly consumes exact content-hashed reviewed
semantic-target artifacts and writes one health snapshot and request envelope
only after strict identity, freshness, authorization, aggregation, and dry-run
account validation. It does not run the supervisor or connect to deployment.
See [local_supervised_provider_assembly.md](local_supervised_provider_assembly.md).

The checked-in API-only, no-network rehearsal verifies the local provider
assembly. On June 15, 2026, all seven scenarios passed, all 68 linked evidence
paths verified, one assembled provider input completed one supervised dry-run
cycle, and no order, fill, semantic-paper, or Alpaca directory appeared. See
[local_supervised_provider_assembly_rehearsal.md](local_supervised_provider_assembly_rehearsal.md).

The current uncommitted review bundle adds
`quant dry-run supervised-provider`, a manually started command that consumes
one content-bound reviewed request, assembles exact local provider inputs, and
runs exactly one supervised dry-run cycle. On June 15, 2026, the actual
command completed twice with the same durable result and produced 20 evidence
files with no order, fill, semantic-paper, or Alpaca directory. See
[supervised_provider_operator.md](supervised_provider_operator.md).

On June 14, 2026, the command passed one local synthetic operator rehearsal.
Running the same request twice produced one durable `would_submit` observation
for an intended `BUY 2 AAPL` order and created no paper, order, or fill
directories in the operator output. See
[activated_dry_run_operator_rehearsal.md](activated_dry_run_operator_rehearsal.md).

On June 14, 2026, the read-only inspection command also passed a separate
local synthetic rehearsal. Running inspection twice produced the same
explanation, left all 137 prerequisite files hash-identical, created no
operator activation or output directory, and consumed no activation. See
[activated_dry_run_request_inspection_rehearsal.md](activated_dry_run_request_inspection_rehearsal.md).

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
4. review the API-only supervised dry-run service and its no-network
   rehearsal;
5. review the supervised health and fresh-request provider contracts;
6. review the local supervised provider assembly and its no-network rehearsal;
7. review the manually started supervised-provider dry-run operator boundary;
8. separately review any runtime-clone or recurring scheduler exposure;
9. obtain explicit approval before every broker order-capable rehearsal.

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
