# Current System Status

This is the canonical current-state summary for the repository. It describes
checked-in source capabilities, not the current contents of a broker account,
runtime clone, or loaded service. Those operational facts must be verified
separately from fresh read-only evidence.

## Source Baseline

- Branch: `main`
- Reviewed source commit before this uncommitted manual-operator run bundle:
  `56b45cc`
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
- API-only supervised-provider request discovery that turns reviewed
  one-cycle request files into one exact finite manifest with immutable
  completed or blocked evidence, without running the loop;
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

The checked-in `quant dry-run supervised-provider` command consumes
one content-bound reviewed request, assembles exact local provider inputs, and
runs exactly one supervised dry-run cycle. On June 15, 2026, the actual
command completed twice with the same durable result and produced 20 evidence
files with no order, fill, semantic-paper, or Alpaca directory. See
[supervised_provider_operator.md](supervised_provider_operator.md).

The checked-in evidence-verified actual-command rehearsal covers fresh
completion, restart reuse, stale-input blocking, and changed-input blocking.
All four scenarios passed across five command invocations. The report linked
46 scenario evidence paths and found no order, fill, semantic-paper, or Alpaca
directory. See
[supervised_provider_operator_rehearsal.md](supervised_provider_operator_rehearsal.md).

The checked-in `quant dry-run supervised-provider-finite` command processes
one exact ordered list of independently fresh one-cycle requests and stops on
the first block. On June 15, 2026, the actual command completed a two-request
list twice with one durable summary, then separately completed 1/3 requests
before blocking on a stale second request and leaving the third request
untouched. See
[finite_supervised_provider.md](finite_supervised_provider.md).

The checked-in evidence-verified actual-command rehearsal for the finite
supervised-provider command passed exact-list completion, restart reuse,
preflight rejection, and stop-on-block across five command invocations. The
report linked 119 scenario evidence paths, bound 120 Python source files, and
found no order, fill, semantic-paper, or Alpaca directory. See
[finite_supervised_provider_rehearsal.md](finite_supervised_provider_rehearsal.md).

The checked-in API-only supervised-provider request discovery scans one
reviewed directory for `*.json` one-cycle operator requests, verifies request
and linked assembly evidence, and writes one finite manifest plus a durable
completed or blocked discovery result. It does not run the finite loop and has
no CLI, scheduler, runtime, paper, Alpaca, broker, or order capability. See
[supervised_provider_discovery.md](supervised_provider_discovery.md).

The checked-in no-network discovery handoff rehearsal proves
discovery-to-loop completion, restart reuse, empty-directory block, over-limit
block, changed-input block, and finite-loop stop-on-block handoff without
adding operational exposure. On June 16, 2026, the local rehearsal passed all
six scenarios, bound 122 Python source files, linked 122 scenario evidence
paths, verified six discovery results, three finite manifests, three finite
loop records, and found no order, fill, semantic-paper, or Alpaca directory.
See
[supervised_provider_discovery_rehearsal.md](supervised_provider_discovery_rehearsal.md).

The checked-in manually started `quant dry-run supervised-provider-discover`
command consumes one reviewed discovery request, verifies the exact
discovery-handoff rehearsal, runs discovery only, writes one operator record,
and exits nonzero when discovery blocks. It may write a finite manifest but
does not run it, and it has no scheduler, runtime, paper, Alpaca, broker, mode,
output-root, or iteration selector. See
[supervised_provider_discovery_operator.md](supervised_provider_discovery_operator.md).

The checked-in actual-command rehearsal for the discovery-only CLI covers
fresh completion, restart reuse, blocked discovery, and tampered rehearsal
rejection while verifying no finite-loop execution or operational output. On
June 17, 2026, the local actual-command rehearsal passed all four scenarios,
bound 124 Python source files, captured five command observations, verified
three operator records, linked 301 scenario evidence paths, and found no
order, fill, semantic-paper, or Alpaca directory. See
[supervised_provider_discovery_operator_rehearsal.md](supervised_provider_discovery_operator_rehearsal.md).

The checked-in manually started
`quant dry-run supervised-provider-discover-finite` command consumes one
reviewed composition request, verifies the discovery-only command rehearsal,
runs one reviewed discovery-only operator request, and then runs only the
exact finite manifest produced by discovery. It writes one composition record,
exits nonzero on discovery or finite-loop blocks, and has no scheduler,
runtime, paper, Alpaca, broker, mode, output-root, or iteration selector. See
[supervised_provider_discovery_loop_operator.md](supervised_provider_discovery_loop_operator.md).

The checked-in actual-command rehearsal for
`quant dry-run supervised-provider-discover-finite` ran on June 19, 2026 local
time and passed completion, restart reuse, blocked discovery, blocked finite
loop, and tampered prerequisite rejection. The report bound 126
Python source files, captured six command observations, verified four
composition records, linked 1,519 scenario evidence paths, and found no order,
fill, semantic-paper, or Alpaca directory. See
[supervised_provider_discovery_loop_rehearsal.md](supervised_provider_discovery_loop_rehearsal.md).

The checked-in source-only promotion boundary defines the review line for that
command. Promotion means considering a stronger operational use than the
current manual dry-run command; it does not authorize trading, runtime-clone
mutation, launchd loading, recurring scheduling, semantic local paper, Alpaca,
broker access, or order submission. See
[supervised_provider_discovery_loop_promotion_boundary.md](supervised_provider_discovery_loop_promotion_boundary.md).

The checked-in source-only promotion review accepts the checked-in command,
actual-command rehearsal, and promotion boundary as enough evidence to design
a runtime-clone copy rehearsal. It does not authorize copying to the runtime
clone, running workflows, loading launchd, recurring scheduling, semantic
local paper, Alpaca, broker access, or order submission. See
[supervised_provider_discovery_loop_source_promotion_review.md](supervised_provider_discovery_loop_source_promotion_review.md).

The checked-in runtime-clone copy rehearsal design is limited to clean-state
checks, scheduler-unloaded checks, fast-forward planning, package import, and
CLI help verification. It does not authorize running workflows, sourcing
credentials, loading launchd, recurring scheduling, semantic local paper,
Alpaca, broker access, or order submission. See
[supervised_provider_discovery_loop_runtime_copy_rehearsal_design.md](supervised_provider_discovery_loop_runtime_copy_rehearsal_design.md).

The checked-in runtime-copy rehearsal attempt initially blocked. Read-only
preflight found the development workspace clean and the Alpaca paper launchd
service unloaded, but the runtime clone had unrelated web-app modifications
and `data/web/`. Those runtime-clone changes were preserved in `stash@{0}`
with the message
`runtime-clone-web-app-wip-before-discovery-loop-rehearsal-2026-06-23`.

The checked-in runtime-copy import/help rehearsal fast-forwarded the clean
runtime clone from `5da3147` to `1a31de6`, package import passed, and command
help for
`quant dry-run supervised-provider-discover-finite` passed. The runtime clone
remained clean after the checks, `data/web`, `data/semantic-target`,
`data/scheduler`, and `data/paper` remained absent, and no workflow execution,
credentials, launchd, scheduler, paper, Alpaca, broker, order, or fill
activity occurred. See
[supervised_provider_discovery_loop_runtime_copy_rehearsal.md](supervised_provider_discovery_loop_runtime_copy_rehearsal.md).

The checked-in runtime-clone no-network actual-command rehearsal design runs
the existing synthetic-input rehearsal generator from the runtime clone, writes
evidence under `/tmp`, and excludes runtime data writes, `.env`, credentials,
launchd, scheduler, paper, Alpaca, broker, orders, and fills. See
[supervised_provider_discovery_loop_runtime_command_rehearsal_design.md](supervised_provider_discovery_loop_runtime_command_rehearsal_design.md).

The checked-in runtime-clone no-network actual-command rehearsal ran from the
runtime clone at `8d1398a`, wrote
evidence under `/tmp/quant-runtime-discovery-loop-command-rehearsal`, passed
all five scenarios, captured six command observations and four composition
records, linked 1,519 evidence paths, and found zero prohibited artifacts. The
runtime clone remained clean, the preserved web-app stash remained intact,
runtime operational directory timestamps did not change, and no `.env`,
credentials, launchd, scheduler, paper, Alpaca, broker, order, or fill path
was used. See
[supervised_provider_discovery_loop_runtime_command_rehearsal.md](supervised_provider_discovery_loop_runtime_command_rehearsal.md).

The checked-in manual operator runbook design covers request prechecks,
scheduler-unloaded checks, runtime directory snapshots, the exact manual
command, archival requirements, pass/block criteria, and explicit
non-authorization for launchd, recurring scheduling, semantic local paper,
Alpaca, broker access, orders, and fills. See
[supervised_provider_discovery_loop_manual_operator_runbook_design.md](supervised_provider_discovery_loop_manual_operator_runbook_design.md).

The current uncommitted review bundle records one manually started synthetic
discovery-to-loop dry-run request from the runtime clone. The runtime clone ran
at `56b45cc`, the request and all outputs lived under
`/tmp/quant-runtime-manual-discovery-loop-request`, the command exited `0`,
the composition record verified as completed, and runtime operational
directory timestamps did not change. No `.env`, credentials, launchd,
scheduler, semantic local paper, Alpaca, broker, order, or fill path was used.
See
[supervised_provider_discovery_loop_manual_operator_run.md](supervised_provider_discovery_loop_manual_operator_run.md).

The same review bundle adds a manual synthetic readiness review. It concludes
that the system is ready only for manual synthetic dry-run readiness and should
stop this promotion sequence unless a concrete non-synthetic request is
proposed with a separate design. It does not authorize production request
preparation, launchd, recurring scheduling, semantic local paper, Alpaca,
broker access, orders, or fills. See
[supervised_provider_discovery_loop_manual_synthetic_readiness_review.md](supervised_provider_discovery_loop_manual_synthetic_readiness_review.md).

The current review bundle also restarts strategy research. The plan returns to
research-only candidate evaluation, beginning with refreshed baselines,
target-native trend following, volatility-adjusted exposure, a mean-reversion
counterweight, and a simple regime filter. It confines work to research/data
artifacts and does not authorize runtime, launchd, scheduler, paper, Alpaca,
broker, order, or fill paths. See
[strategy_research_restart_plan.md](strategy_research_restart_plan.md).

The source now includes a `ResearchBatchSpec` and immutable research-batch
artifact helpers. A batch groups reviewed candidate specs before experiments
run and carries explicit false guardrails for broker access, runtime mutation,
scheduler use, and order submission. This is still research-only
infrastructure; it does not make the semantic paper pipeline ready.

The source also defines the first AAPL research batch builder. It produces five
candidate specs: momentum baseline, feature-momentum baseline, target-native
trend, volatility-adjusted trend, and mean-reversion counterweight. The builder
is pure and requires validated AAPL market-bar and feature input snapshots
before a durable batch artifact or backtest can be produced.

The research batch materializer now validates AAPL market bars, loads AAPL
technical features, requires the `ma_5` and `ma_20` columns, computes input
hashes, and writes the immutable batch artifact. It does not fetch data, run
backtests, touch runtime state, use broker credentials, or submit orders.

The first AAPL research batch artifact has been materialized under
`data/research/strategy-batches/aapl-strategy-research-batch-v1/`. It uses
1006 validated historical AAPL market-bar rows for 2020-01-01 through
2024-01-01, generated technical features with matching row count, and verifies
through the immutable batch manifest. The captured input hashes are:
`b21ba6ad44dcb408e8937f984d280f82a6d9c2e2a992f9a1cd69e6b8ed3720a2` for
market bars and
`fe9895a8bc2e3ec6909b49c577ddfd8c6c64427ae728577b824635a80e7d4c55` for
features.

The first research evaluation run created five evaluation directories under
`data/research/evaluations/`. The supported legacy momentum and
feature-momentum baselines both completed with total return `1.227483`, final
value `222748.28`, 25 trades, and max drawdown `-0.21010632998879852`; this
confirms that the feature-backed baseline currently reproduces the price
baseline on the same AAPL input. The target-native trend,
volatility-adjusted trend, and mean-reversion candidates were recorded as
abandoned trials because their concrete research strategy implementations are
not available yet. No paper, broker, scheduler, runtime, order, or fill path
was used.

The target-native research strategies are now implemented and the AAPL batch
was rerun append-only. Each candidate has two trial-ledger entries: the prior
baseline/abandoned evidence and a new successful `trial-v2`. Latest metrics:
target-native trend returned `0.000873` with final value `100087.34`, 50
trades, and max drawdown `-0.00041419746904647337`; volatility-adjusted trend
returned `0.000673` with final value `100067.25`, 247 trades, and max drawdown
`-0.00043478379509664933`; mean-reversion counterweight returned `-0.000967`
with final value `99903.32`, 43 trades, and max drawdown
`-0.0011619116433893018`. Target-history CSV artifacts were persisted for all
three target-native candidates.

The first AAPL research report is now written under
`data/research/reports/aapl-strategy-research-batch-v1/`. It passes the legacy
momentum baseline as the control and feature momentum for parity. The three
target-native candidates fail promotion from this batch because they do not
beat or sufficiently justify a tradeoff against the control baseline. The
report explicitly authorizes no dry-run, paper, Alpaca, broker, scheduler,
runtime, order, or fill path.

The source now includes a second research-only AAPL batch definition,
`aapl-strategy-research-batch-v2`, for the next batch materialization. V1
remains the historical five-candidate batch that produced the current report.
V2 adds a declared-notional target trend candidate that keeps sizing inside the
strategy by declaring target notional exposure and resolving that exposure to
signed share targets from current price.

The v2 batch artifact is now materialized under
`data/research/strategy-batches/aapl-strategy-research-batch-v2/`, with
evaluations under `data/research/evaluations-v2/` and a report under
`data/research/reports/aapl-strategy-research-batch-v2/`. The declared-notional
candidate returned `0.680071` with final value `168007.15`, 532 trades, max
drawdown `-0.2111674998627756`, and Sharpe `0.744340`. It improves on the
earlier target-native candidates but still fails promotion because it trails
the legacy momentum control, slightly worsens drawdown, and trades too often.
The v2 report authorizes no dry-run, paper, Alpaca, broker, scheduler,
runtime, order, or fill path.

The source now includes a third research-only AAPL batch definition,
`aapl-strategy-research-batch-v3`. V3 preserves the v2 candidates and adds a
hysteresis declared-notional target trend candidate. The new candidate keeps
strategy-owned notional sizing but adds entry and exit spread bands so small
moving-average spread changes do not immediately flip exposure.

The v3 batch artifact is now materialized under
`data/research/strategy-batches/aapl-strategy-research-batch-v3/`, with
evaluations under `data/research/evaluations-v3/` and a report under
`data/research/reports/aapl-strategy-research-batch-v3/`. The hysteresis
candidate returned `0.418560` with final value `141856.03`, 488 trades, max
drawdown `-0.23307565652185935`, and Sharpe `0.567468`. It reduced turnover
versus the v2 declared-notional candidate, but only from 532 to 488 trades
while lowering return and worsening drawdown. It fails promotion and authorizes
no dry-run, paper, Alpaca, broker, scheduler, runtime, order, or fill path.

The source now includes a fourth research-only AAPL batch definition,
`aapl-strategy-research-batch-v4`. V4 preserves the v3 candidates and adds a
rebalance-band notional trend candidate. This candidate keeps notional sizing
inside the strategy but avoids resizing the signed share target until the
current target has drifted at least `5%` from the ideal notional-derived share
target.

The v4 batch artifact is now materialized under
`data/research/strategy-batches/aapl-strategy-research-batch-v4/`, with
evaluations under `data/research/evaluations-v4/` and a report under
`data/research/reports/aapl-strategy-research-batch-v4/`. The rebalance-band
candidate returned `0.709748` with final value `170974.83`, 101 trades, max
drawdown `-0.2087666409999036`, and Sharpe `0.767985`. It is the strongest
target-native result so far because it materially reduces turnover and improves
return, drawdown, and Sharpe versus the v2 declared-notional candidate.
However, it still trails the legacy momentum control on total return and
Sharpe, so it is promising research evidence rather than operational
authorization. The v4 report authorizes no dry-run, paper, Alpaca, broker,
scheduler, runtime, order, or fill path.

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

The source now exposes a bounded local semantic-paper operator boundary through
`quant semantic-paper activated-target`. The command consumes one reviewed
activated request artifact, verifies activation-consumption rehearsal evidence,
hardcodes local paper safety, and writes durable semantic-paper state, order,
fill, reconciliation, lifecycle, and orchestration evidence. It is intended as
the P0 infrastructure path for translated strategy targets. It exposes
no Alpaca, scheduler, runtime, mode, or broker-network selector. The companion
`quant semantic-paper inspect-activated-target` command explains the request
without writing files or consuming activation.

On June 26, 2026, the activated local semantic-paper command passed its first
synthetic translated-momentum canary rehearsal. Inspection wrote no artifacts.
Running the exact same request twice reached `execution_completed` and
`satisfied`, leaving one local semantic-paper order, one fill, one
reconciliation report, one orchestration record, and final AAPL local-paper
position `+2`. See
[activated_semantic_paper_operator_rehearsal.md](activated_semantic_paper_operator_rehearsal.md).

The source now includes `quant semantic-paper prepare-momentum-request`. It
validates a local market-bar CSV, runs the legacy momentum strategy, translates
the latest signal into a whole-share semantic target, and writes a reviewed
local semantic-paper request bundle. The command prepares evidence only; it
does not execute local paper, contact Alpaca, load a scheduler, mutate runtime,
or submit broker-network orders.

On June 26, 2026, the request generator passed its first local-data rehearsal
against `data/normalized/market_bars/AAPL.csv`. The latest legacy momentum
signal was `hold` on `2023-12-29`, so the reviewed request targeted flat `AAPL`
from an already-flat local-paper state. Inspection reported no intended order,
and two local semantic-paper runs reused the same orchestration and reached
`execution_completed` / `satisfied` with zero orders and zero fills. See
[momentum_semantic_paper_request_rehearsal.md](momentum_semantic_paper_request_rehearsal.md).

On June 26, 2026, the request generator also passed a nonzero local request
rehearsal with temporary deterministic AAPL market data. The latest legacy
momentum signal was `buy`, so the reviewed request targeted `AAPL +2`.
Inspection reported an intended `BUY 2 AAPL` order. Two local semantic-paper
runs reused the same orchestration and reached `execution_completed` /
`satisfied`, leaving one local-paper order, one fill, and final AAPL local-paper
position `+2`. See
[momentum_semantic_paper_nonzero_request_rehearsal.md](momentum_semantic_paper_nonzero_request_rehearsal.md).

The next reviewed design is a runtime-clone import/help-only rehearsal for the
semantic-paper command family. It would verify that the reviewed source can be
fast-forwarded into the runtime clone, imported, and asked for CLI help without
generating requests, running local semantic paper, loading launchd, using
credentials, contacting Alpaca, or touching broker-network paths. See
[semantic_paper_runtime_copy_rehearsal_design.md](semantic_paper_runtime_copy_rehearsal_design.md).

On June 26, 2026, that runtime-clone import/help-only rehearsal passed. The
clean runtime clone fast-forwarded from `56b45cc` to reviewed source `2614ebc`.
With bytecode writing disabled, package import and semantic-paper CLI help
succeeded. The runtime clone stayed clean, `data/semantic-target` remained
absent, no request generation or local semantic-paper command was run, and no
new `__pycache__` directories were created. See
[semantic_paper_runtime_copy_rehearsal.md](semantic_paper_runtime_copy_rehearsal.md).

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
8. review its evidence-verified actual-command rehearsal;
9. review the finite fresh supervised-provider operator boundary;
10. review its evidence-verified actual-command rehearsal;
11. review the discovery-to-loop operator boundary and actual-command
    rehearsal;
12. review the checked-in source-only promotion boundary;
13. review the checked-in source-only promotion review;
14. review the checked-in runtime-clone copy rehearsal design;
15. review the checked-in runtime-clone copy/import/help rehearsal evidence;
16. review the checked-in runtime-clone no-network command rehearsal design;
17. review the checked-in runtime-clone no-network command rehearsal evidence;
18. review the checked-in manual operator runbook design;
19. review the manual synthetic operator run evidence and readiness review;
20. stop this promotion sequence unless a concrete non-synthetic request is
    proposed with a separate design;
21. review the research-batch contract and immutable batch artifact helpers;
22. resume research-only strategy candidate evaluation under the restart plan;
23. separately review any runtime-clone or recurring scheduler exposure;
24. obtain explicit approval before every broker order-capable rehearsal.

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
