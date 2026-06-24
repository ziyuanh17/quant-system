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
  -> refresh or locate validated AAPL data
  -> run baseline and target-native simulations
  -> persist immutable evaluation artifacts
  -> write a research report with pass/fail decisions
```

Do not connect any passing candidate to dry-run, paper, Alpaca, scheduler, or
runtime operation without a later promotion review.
