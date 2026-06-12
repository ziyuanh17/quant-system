# Strategy Evaluation Harness Design

This document designs a repeatable research-to-paper evaluation path for
candidate strategies. The harness is research-only. It must not submit orders,
read broker credentials, alter runtime artifacts, or change scheduler state.

## Objective

Replace one-off backtest interpretation with a durable process that answers:

```text
what was tested
  -> against which exact data and features
  -> with which parameters and costs
  -> across which time periods
  -> compared with which baselines
  -> under which promotion criteria
```

The harness should make promising strategies easier to reproduce and weak or
overfit strategies easier to reject.

## Position In The System

The harness is the research-governance layer between backtesting and any
paper-promotion decision:

```text
data and feature lineage
  -> strategy research and simulation
  -> evaluation harness
  -> reviewed promotion recommendation
  -> separate paper-promotion process
```

Backtesting answers how one configured simulation behaved. The evaluation
harness answers whether the complete body of research evidence is reproducible,
comparable, statistically credible, and sufficient for a promotion review.

This layer is important in a modern quant system because inexpensive parameter
search can produce convincing but false discoveries. A strong simulation
engine without experiment tracking, leakage controls, trial accounting, and
promotion governance makes overfitting easier rather than safer.

## Current Foundation

The repository already provides:

- validated normalized market-bar inputs,
- persisted technical feature artifacts,
- price-based and feature-based strategy protocols,
- `momentum` and `feature-momentum` strategies,
- VectorBT-backed signal backtests,
- typed backtest configuration and performance metrics,
- durable `summary.json` and `trades.csv` artifacts.

The current backtest path remains the simulation engine. The harness should
compose and compare backtest runs instead of introducing another portfolio
engine.

## Design Assessment

The existing repository has a strong foundation for a small system:

- typed boundaries and durable artifacts are already preferred over notebooks
  and implicit dictionaries,
- research and broker execution are separated,
- data validation and lineage exist before strategy evaluation,
- VectorBT is treated as a replaceable simulation engine rather than the whole
  application.

The current strategy and backtest contracts are still narrow:

- strategies emit entry and exit booleans directly,
- one strategy owns alpha generation, position intent, and exit behavior,
- backtests are one-symbol and one-path,
- summaries do not persist daily returns, equity curves, code identity, input
  content hashes, or all trials considered,
- a single holdout split cannot quantify selection bias after many trials.

The harness should preserve the simple path while adding general interfaces
around it. Existing `Strategy` and `FeatureStrategy` implementations should be
supported through adapters rather than rewritten immediately.

The first semantic-target foundation is defined in
[semantic_target_architecture.md](semantic_target_architecture.md). Native
target strategies and legacy-equivalence evidence are research-only; they do
not authorize paper or broker execution.

## Safety Boundary

The evaluation harness may read research artifacts and write new research
artifacts under `data/research/`.

It must not:

- import or construct broker clients,
- read `.env` or Alpaca credentials,
- write under `data/live/`, `data/paper/`, or runtime-clone paths,
- invoke paper, dry-run, or live execution commands,
- load, unload, or inspect launchd jobs,
- automatically promote a strategy into scheduled execution.

Promotion means producing a reviewed recommendation artifact. Enabling a
strategy in paper execution remains a separate milestone and explicit decision.

## Evaluation Unit

One candidate evaluation must be defined by a versioned specification:

```text
candidate ID
research family ID and hypothesis ID
strategy name and implementation version
serialized strategy parameters
symbol universe
input dataset and feature artifact references
date range and split policy
initial cash, fees, and slippage assumptions
benchmark
promotion criteria version
human-readable hypothesis
source commit, dependency-lock hash, and random seed
```

Candidate IDs should be stable and content-derived or explicitly supplied.
Wall-clock time alone is not a sufficient identity because the same candidate
must be reproducible later.

Every attempted candidate or parameter variation must be recorded in a trial
ledger, including failed and abandoned trials. Recording only the best run
makes multiple-testing adjustments and honest review impossible.

## Modular Research Architecture

Different strategy families should share evaluation machinery without being
forced into one signal shape:

```text
ResearchDataView
  -> AlphaModel
  -> PortfolioConstructionModel
  -> RiskOverlay
  -> SimulationModel
  -> EvaluationPolicy
```

- `ResearchDataView` resolves point-in-time-correct prices, features, universe,
  and lineage references.
- `AlphaModel` produces typed forecasts, rankings, expected returns, or direct
  signal intents.
- `PortfolioConstructionModel` converts alpha output into target positions or
  weights.
- `RiskOverlay` constrains target positions independently of alpha generation.
- `SimulationModel` applies costs, slippage, fills, delays, and market rules.
- `EvaluationPolicy` computes evidence and promotion criteria without knowing
  strategy internals.

The first implementation does not need all modules. It should define a
`StrategyEvaluator` boundary and adapt the existing entry/exit strategies into
it. Later implementations can add modules only when a strategy family needs
them.

This separation supports:

- technical entry/exit strategies through a signal adapter,
- cross-sectional ranking and factor strategies,
- forecast or machine-learning strategies,
- multi-asset allocation strategies,
- event-driven strategies,
- long-only, long/short, and market-neutral portfolio policies.

Strategies with tightly coupled entry and exit logic may keep a combined
strategy adapter. Modularity must not force every strategy into an unnatural
shape.

## Evaluation Workflow

```text
define candidate specification
  -> validate data and feature prerequisites
  -> register every intended trial
  -> freeze evaluation splits
  -> run baseline and candidate backtests
  -> calculate comparison and robustness metrics
  -> calculate multiple-testing and leakage evidence
  -> evaluate promotion criteria
  -> write immutable evaluation artifacts
  -> review recommendation
```

The first version should evaluate one strategy on one symbol at a time while
keeping the artifact shape ready for later multi-symbol aggregation.

## Time-Split Policy

Every candidate must be evaluated on ordered, non-overlapping time periods:

```text
development period
validation period
holdout period
```

- The development period may be used to choose initial parameters.
- The validation period may be used to compare a small, declared parameter
  set.
- The holdout period must remain untouched until the candidate and promotion
  criteria are frozen.

Random row splits are not allowed for time-series evaluation. Future versions
should add walk-forward and purged/embargoed cross-validation, but the first
version should establish the artifact and review discipline before adding
optimization machinery.

A simple development/validation/holdout split is an initial discipline, not a
complete defense against backtest overfitting. When many variants are tested,
the harness should support combinatorial or purged evaluation that produces a
distribution of out-of-sample outcomes rather than relying on one favorable
historical path.

## Point-In-Time Correctness

Every research input must identify both:

```text
event time
availability time
```

The harness must reject features, universe membership, fundamentals, news, or
other data that cannot prove what would have been available at the simulated
decision time. Dataset paths alone are not enough; content hashes, schema
versions, provider/normalizer versions, and point-in-time policy should be
persisted.

Corporate actions, delistings, symbol mappings, and historical universe
membership must be explicit before multi-symbol promotion evidence is trusted.

## Baselines

Every evaluation must include at least:

- a buy-and-hold baseline for the same symbol and period,
- the current reviewed strategy configuration when one exists,
- the candidate strategy.

Comparisons must use the same data range, initial cash, fees, and execution
assumptions. A candidate does not pass merely because its total return is
positive.

## Metrics

The existing metrics remain required:

```text
total return
Sharpe ratio
maximum drawdown
total trades
final value
```

The first harness implementation should add:

```text
annualized return
annualized volatility
Calmar ratio
win rate
profit factor
average trade return
exposure percentage
turnover or trade-frequency proxy
benchmark excess return
daily return series and equity curve
skewness and kurtosis
probabilistic or deflated Sharpe evidence when applicable
```

Metrics must be reported separately for development, validation, and holdout
periods. Aggregate metrics must never hide a failed holdout period.

## Robustness Checks

The first version should fail closed when required evidence is unavailable and
should report, at minimum:

- sensitivity to a small declared parameter neighborhood,
- sensitivity to higher fee assumptions,
- minimum data coverage and trade count,
- performance concentration by time period,
- comparison against buy-and-hold,
- validation and holdout degradation relative to development.

For every research family, the trial ledger should report the number of
attempted and effectively distinct trials. Once multiple variants are compared,
promotion evidence should include a multiple-testing-aware measure such as the
Deflated Sharpe Ratio and, for sufficiently broad searches, an estimate of
backtest-overfitting probability.

Later versions can add multi-symbol evaluation, walk-forward analysis,
purged/embargoed cross-validation, combinatorial cross-validation, bootstrap
confidence intervals, regime analysis, capacity analysis, and provider
reconciliation as explicit extensions.

## Scenario And Reality Modeling

Strategy quality and simulation quality must be reported separately. Evaluation
should run the same strategy under versioned simulation scenarios:

```text
base costs
higher fees and slippage
delayed execution
reduced liquidity or participation cap
missing-data or stale-feature behavior
short availability and borrow-cost assumptions when applicable
```

The strategy candidate must not own these assumptions. Shared simulation
scenarios make comparisons fair and allow execution-model improvements without
rewriting alpha logic.

## Promotion Criteria

Promotion criteria must be versioned and declared before revealing holdout
results. Initial criteria should be conservative and configurable rather than
hard-coded as universal trading truths.

A candidate recommendation may be `reject`, `revise`, or
`recommend-for-paper-review`.

The first criteria set should require:

1. All input data and features pass validation and have identifiable paths.
2. No evaluation step uses future data or overlapping time splits.
3. Validation and holdout metrics are present.
4. Holdout total return and risk-adjusted return exceed declared minimums.
5. Holdout maximum drawdown stays within the declared limit.
6. Results remain acceptable under the higher-fee scenario.
7. The strategy produces enough trades to make its metrics interpretable,
   without relying on excessive turnover.
8. Performance is not dominated by one short interval or one trade.
9. The candidate improves on or clearly complements its declared baseline.
10. Trial count and multiple-testing evidence are disclosed.
11. Point-in-time availability and universe policy are documented.
12. Every failed criterion is visible in the recommendation artifact.

Passing criteria does not authorize paper execution. It only makes the
candidate eligible for a separate paper-promotion review.

## Artifacts

Each evaluation should write to an immutable candidate/run directory:

```text
data/research/evaluations/<candidate-id>/<evaluation-id>/
  candidate.json
  environment.json
  inputs.json
  splits.json
  trials.jsonl
  baseline/
    summary.json
    trades.csv
  candidate/
    development/
      summary.json
      trades.csv
    validation/
      summary.json
      trades.csv
    holdout/
      summary.json
      trades.csv
  robustness.json
  returns.csv
  equity_curve.csv
  scenarios/
  comparison.json
  recommendation.json
```

`recommendation.json` should contain the criteria version, pass/fail result for
every criterion, final recommendation, and evidence paths. It must not contain
credentials or broker state.

## Typed Model Boundary

The first implementation should introduce typed models for:

- `StrategyCandidateSpec`,
- `ResearchInputSnapshot`,
- `ResearchTrialRecord`,
- `EvaluationSplitPolicy`,
- `SimulationScenario`,
- `EvaluationRunRecord`,
- `StrategyComparisonReport`,
- `PromotionCriterionResult`,
- `StrategyPromotionRecommendation`.

Strategy parameters should be serialized from typed configuration models. The
harness should not depend on arbitrary dictionaries whose keys must be traced
through the system manually.

Backend storage should remain replaceable. The first version can use typed
JSON/CSV artifacts and content hashes; a later adapter may publish the same
runs to an experiment-tracking system without changing evaluation logic.

## Proposed CLI Boundary

The first implementation may expose research-only commands such as:

```text
quant research evaluate --candidate path/to/candidate.json
quant research compare --evaluation-dir path/to/evaluation
quant research recommend --evaluation-dir path/to/evaluation
quant research audit --evaluation-dir path/to/evaluation
```

These commands must remain separate from `quant paper`, `quant dry-run`,
`quant live`, `quant workflow`, and `quant schedule`.

## Review Gates

Before implementation:

- review the candidate, split, comparison, and recommendation artifact schemas,
- choose an initial promotion-criteria configuration,
- decide how exact input artifact IDs will be represented,
- decide whether slippage is implemented in the backtester or represented as a
  fee-sensitivity scenario first.
- define the minimal shared evaluator output: returns, equity curve, positions,
  trades, and diagnostics,
- define trial-family accounting before any parameter sweep is introduced.

Before any candidate reaches paper execution:

- review complete evaluation artifacts,
- rerun from a clean development clone,
- verify holdout isolation,
- document the operational risk policy,
- create a separate paper-promotion milestone.

## Recommended Implementation Order

```text
typed candidate and evaluation models
  -> evaluator protocol and existing-strategy adapter
  -> immutable research artifact writer
  -> trial ledger and reproducibility manifest
  -> deterministic time-split runner
  -> baseline comparison report
  -> shared simulation scenarios
  -> configurable promotion criteria
  -> research CLI
  -> fake-data tests
  -> one documented candidate evaluation
```

The first implementation should stay one-symbol and deterministic. Multi-symbol
portfolio construction, parameter optimization, and automatic paper promotion
are intentionally deferred.

## Initial Foundation Outcome

The first implementation slice introduces:

- typed candidate, input snapshot, split policy, simulation scenario, and trial
  ledger models,
- validation for input content hashes, point-in-time availability policy,
  non-overlapping ordered splits, unique candidate components, and terminal
  trial completion,
- a normalized `StrategySimulationInput` contract,
- price-strategy and feature-strategy adapters for the existing strategy
  protocols,
- focused tests for both governance rules and existing-strategy compatibility.

This slice does not run evaluations, write research artifacts, sweep
parameters, calculate promotion metrics, or connect research to execution.

## Immutable Artifact Foundation Outcome

The second implementation slice introduces:

- full-content SHA-256 evaluation IDs derived from the typed candidate and
  environment snapshots,
- exclusive creation of candidate-scoped evaluation directories,
- immutable candidate, environment, input, split, and scenario artifacts,
- a checksum manifest regenerated from typed source content during audit,
- fail-closed detection of changed, missing, or manifest-mismatched immutable
  artifacts,
- an append-only JSONL trial ledger that records successful, failed, and
  abandoned trials,
- duplicate trial ID, candidate mismatch, research-family mismatch, unsafe
  path, and environment mismatch rejection.

Appending a trial first verifies the immutable evaluation artifacts. The V1
ledger assumes one research writer at a time; future parallel evaluation work
must introduce an explicit research-family lock or transactional ledger before
concurrent writers are allowed.

This slice does not execute a strategy simulation, calculate metrics, expose a
research CLI, or connect research artifacts to execution.

## Staged Scope

To keep this system solo-maintainable, adopt state-of-the-art controls in
layers:

### Required In V1

- typed candidate specification and evaluator output,
- immutable artifacts with code, dependency, input, and parameter identity,
- trial ledger that records every attempted variant,
- ordered development/validation/holdout splits,
- daily returns, equity curve, positions, trades, and diagnostics,
- baseline and cost-scenario comparison,
- configurable recommendation criteria,
- existing strategy adapter,
- no broker or scheduler connection.

### Required Before Broad Parameter Search Or ML Promotion

- purging and embargo policy,
- walk-forward or combinatorial out-of-sample evaluation,
- multiple-testing-aware statistics,
- explicit point-in-time feature availability,
- random-seed and training reproducibility,
- experiment-family comparison rather than best-run-only reporting.

### Required Before Multi-Asset Paper Promotion

- historical universe and delisting policy,
- portfolio construction and risk-overlay interfaces,
- exposure, concentration, liquidity, turnover, and capacity evidence,
- shared reality-model scenarios,
- portfolio-level benchmark and attribution.

## Research Basis

The refinement draws on these durable ideas:

- Experiment tracking systems organize runs around parameters, code versions,
  metrics, datasets, and output artifacts, while registries add lineage,
  versioning, aliases, and controlled lifecycle transitions.
- Point-in-time feature retrieval reconstructs the feature state available at
  each historical event timestamp and is necessary to avoid future leakage.
- The Probability of Backtest Overfitting work shows that ordinary holdout
  methods can be unreliable for investment backtests and proposes
  combinatorially symmetric cross-validation.
- The Deflated Sharpe Ratio corrects performance inflation caused by multiple
  testing, selection bias, and non-normal returns.
- Modular algorithm frameworks separate alpha, portfolio construction, risk,
  and execution so components can be evaluated and reused independently, while
  recognizing that tightly coupled strategies may need an adapter or hybrid
  design.

References:

- MLflow Tracking: <https://mlflow.org/docs/latest/ml/tracking/>
- MLflow Model Registry: <https://mlflow.org/docs/latest/ml/model-registry/>
- Feast point-in-time joins:
  <https://docs.feast.dev/getting-started/concepts/point-in-time-joins>
- Bailey et al., *The Probability of Backtest Overfitting*:
  <https://ssrn.com/abstract=2326253>
- Bailey and Lopez de Prado, *The Deflated Sharpe Ratio*:
  <https://ssrn.com/abstract=2460551>
- QuantConnect Algorithm Framework:
  <https://www.quantconnect.com/docs/v2/writing-algorithms/algorithm-framework/overview>
