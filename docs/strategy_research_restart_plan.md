# Strategy Research Restart Plan

This document restarts strategy research after the discovery-to-loop synthetic
operator promotion sequence.

In plain language: the operator path is now proven far enough for synthetic
manual dry-runs, so the next useful work should return to finding and
evaluating better strategies. This plan does not authorize paper trading,
Alpaca, launchd, scheduler activation, broker access, orders, or fills.

## Current Position

The project already has:

- validated market-bar ingestion and lineage;
- feature artifact generation;
- legacy signal backtests;
- native semantic-target research backtests;
- immutable research artifacts and trial ledger;
- legacy equivalence evidence;
- contributor-set portfolio aggregation;
- independently persisted risk targets;
- dry-run/local-paper/Alpaca semantic execution paths behind separate
  operational gates.

The most recent operator work proved that the discovery-to-loop dry-run command
can run synthetic reviewed requests from the runtime clone without touching
runtime operational paths. That is not strategy evidence. It only means the
manual dry-run tool is bounded.

## Research Boundary

Near-term research may read and write:

```text
data/research/
data/results/
data/features/
data/metadata/
data/validation/
```

Near-term research must not:

- source `.env`;
- read broker credentials;
- run Alpaca commands;
- run local semantic paper;
- run legacy paper workflows;
- run launchd;
- mutate the runtime clone;
- write orders or fills;
- treat a good backtest as execution approval.

## Recommended Research Questions

Start with strategy families that are simple enough to evaluate honestly:

1. **Momentum baseline refresh**
   Re-run the existing momentum and feature-momentum baselines on current
   validated data. This gives a fresh control group.
2. **Target-native trend following**
   Express trend-following directly as signed target positions. Compare target
   simulation against the legacy signal path where equivalence is expected.
3. **Volatility-adjusted exposure**
   Scale target size by recent volatility in research only. Preserve fractional
   research targets and let operational validation reject or quantize later in
   a separate design.
4. **Mean-reversion counterweight**
   Add a simple mean-reversion candidate so portfolio aggregation has at least
   two strategies that can disagree on the same symbol.
5. **Regime filter**
   Test whether a slow market-regime filter improves drawdown without creating
   a fragile parameter trap.

## First Research Batch

The first batch should be intentionally small:

```text
symbol: AAPL
data source: existing validated market bars
families:
  - existing momentum
  - existing feature momentum
  - target-native trend following
  - volatility-adjusted trend following
  - mean-reversion counterweight
```

Use fixed, declared parameter grids. Do not expand the grid after seeing the
results without recording the additional trials as a new batch.

The first batch builder is implemented as
`build_aapl_strategy_research_batch_v1`. It defines these reviewed candidate
IDs:

```text
aapl-momentum-baseline-5-20-v1
aapl-feature-momentum-baseline-5-20-v1
aapl-target-native-trend-5-20-v1
aapl-vol-adjusted-trend-5-20-20-v1
aapl-mean-reversion-counterweight-5-20-v1
```

The builder is pure: it does not read files, refresh data, run backtests,
touch runtime state, or contact a broker. It requires validated AAPL market-bar
and feature input snapshots with real paths and SHA-256 hashes before a batch
artifact can be materialized for actual research.

The materialization helper,
`write_aapl_strategy_research_batch_v1_artifacts`, now performs that gate. It
validates the market-bar CSV, loads the feature CSV, requires the `ma_5` and
`ma_20` feature columns, computes SHA-256 input identities, builds the reviewed
batch, and writes the immutable batch artifact. It does not fetch data or run a
backtest.

The first materialized artifact is:

```text
data/research/strategy-batches/aapl-strategy-research-batch-v1/
```

It references `data/normalized/market_bars/AAPL.csv` and
`data/features/technical/AAPL.csv`, both with 1006 data rows. The batch
manifest verifies, and the batch still carries `order_submission_authorized:
false`.

The first evaluation run used this artifact and created per-candidate
evaluation directories under:

```text
data/research/evaluations/
```

The two implemented legacy baselines completed and produced identical results:
total return `1.227483`, final value `222748.28`, 25 trades, and max drawdown
`-0.21010632998879852`. The three target-native candidates were not simulated
yet; their trial ledgers record `abandoned` because their concrete research
strategy implementations remain the next required source work.

The target-native strategy implementations are now present and the same batch
was rerun. The runner reused the existing immutable evaluation directories and
appended `trial-v2` entries rather than overwriting prior evidence. Latest
target-candidate results:

```text
target-native trend:
  total_return=0.000873
  final_value=100087.34
  trades=50
  max_drawdown=-0.00041419746904647337

volatility-adjusted trend:
  total_return=0.000673
  final_value=100067.25
  trades=247
  max_drawdown=-0.00043478379509664933

mean-reversion counterweight:
  total_return=-0.000967
  final_value=99903.32
  trades=43
  max_drawdown=-0.0011619116433893018
```

The latest run also wrote `targets.csv` for each target-native candidate,
preserving the resolved signed target history used by the target-order
backtest.

The first report and decision artifact are:

```text
data/research/reports/aapl-strategy-research-batch-v1/report.md
data/research/reports/aapl-strategy-research-batch-v1/decision.json
```

The report passes the legacy momentum baseline as the control and feature
momentum for parity. The target-native candidates fail promotion from this
batch because they do not beat or sufficiently justify a tradeoff against the
control baseline.

## Implemented Batch Contract

The repository now has a source-level `ResearchBatchSpec` contract and
immutable research-batch artifact helpers. This object groups reviewed
candidate specs before experiments run. It also keeps the boundary explicit:
broker access, runtime mutation, scheduler use, and order submission are
literal false fields, so a research batch cannot quietly become an operational
authorization.

The batch artifact writer persists:

```text
batch.json
manifest.json
```

under a caller-provided research output root and fails on identity collisions
or unsafe path segments. The verifier reloads the batch, checks the schema
version, confirms the directory and manifest identity, and detects tampering of
the immutable batch artifact.

The AAPL batch builder uses this contract and inherits the same non-operational
boundary. The next implementation step is to locate or refresh validated AAPL
market bars and technical features, compute their hashes, and then persist one
batch artifact under `data/research/`. If no validated AAPL inputs exist
locally, the next step is a research-data refresh only, not a paper or broker
workflow.

`StrategyCandidateSpec` now carries an explicit comparison role. The default
role is `declared_policy`, meaning the strategy is evaluated with its own
declared sizing policy. A `sizing_ablation` candidate intentionally neutralizes
or replaces sizing to inspect timing and direction separately, and the model
requires such candidates to set `promotion_eligible: false`.

Research decision reports now repeat the candidate comparison role and
promotion eligibility, then validate those fields against the reviewed batch
spec. That makes a report auditable on its own while still preventing a
diagnostic ablation from being relabeled as promotion evidence.

## Evidence Required Per Candidate

Each candidate should persist:

- candidate ID and family ID;
- hypothesis;
- strategy implementation version;
- parameter values;
- input data paths and hashes;
- feature artifact paths and hashes, when used;
- split policy;
- fees, slippage, and initial cash;
- source commit;
- dependency lock hash;
- backtest metrics;
- target history or signal history;
- trade list;
- comparison against buy-and-hold and existing momentum;
- comparison role and promotion eligibility;
- pass/fail decision under a declared evaluation policy.

Every attempted parameter variation should enter the trial ledger, including
failed, blocked, or abandoned trials.

## Evaluation Rules

Use ordered time splits:

```text
development
validation
holdout
```

The holdout period must not be inspected until the candidate definition,
parameters, and evaluation criteria are frozen.

A candidate should not pass just because total return is positive. It must
improve at least one useful metric while not degrading drawdown, turnover,
trade count, or robustness beyond the declared tolerance.

## Stop Conditions

Stop the research batch if:

- input data validation fails;
- feature lineage is missing;
- a candidate cannot identify source/data hashes;
- results require changing split periods after inspection;
- the trial ledger omits attempted variants;
- the work starts drifting toward runtime, paper, Alpaca, broker, scheduler,
  order, or fill paths.

## Next Implementation Step

The next implementation should be research-only:

```text
Strategy Research Batch v1
  -> define candidate specs under ResearchBatchSpec
  -> refresh or locate validated AAPL data [done]
  -> materialize the immutable batch artifact [done]
  -> run supported baseline simulations [done]
  -> implement target-native candidate strategies [done]
  -> run target-native simulations [done]
  -> persist immutable evaluation artifacts [done]
  -> write a research report with pass/fail decisions [done]
  -> define fixed-share comparison batch [done]
  -> run fixed-share comparison batch [done]
```

Do not connect any passing candidate to dry-run, paper, Alpaca, scheduler, or
runtime operation without a later promotion review.

## Fixed-Share Comparison

The fixed-share comparison batch is:

```text
data/research/strategy-batches/aapl-fixed-share-comparison-batch-v1/
data/research/fixed-share-evaluations/
```

It compares all candidates through target-order semantics with small
fixed/fractional share targets. This is a sizing ablation: it intentionally
neutralizes strategy-declared sizing so direction and timing can be inspected
separately. It is secondary evidence only. The primary strategy comparison
must respect each strategy's declared sizing policy.

| Candidate | Total Return | Final Value | Trades | Max Drawdown |
| --- | ---: | ---: | ---: | ---: |
| `aapl-fixed-share-momentum-5-20-v1` | `0.000994` | `100099.41` | `25` | `-0.0003782513660368636` |
| `aapl-target-native-trend-5-20-v1` | `0.000873` | `100087.34` | `50` | `-0.00041419746904647337` |
| `aapl-vol-adjusted-trend-5-20-20-v1` | `0.000673` | `100067.25` | `247` | `-0.00043478379509664933` |
| `aapl-mean-reversion-counterweight-5-20-v1` | `-0.000967` | `99903.32` | `43` | `-0.0011619116433893018` |

The fixed-share ablation does not promote target-native candidates and cannot
promote a candidate by itself. The next research work should focus on strategy
design and declared sizing, not operational activation.
