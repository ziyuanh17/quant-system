# Semantic Target Architecture

## Purpose

The semantic-target architecture separates strategy intent from portfolio
construction, risk approval, and broker execution:

```text
strategy evaluation
  -> strategy target decision
  -> contributor-set portfolio aggregation
  -> risk target
  -> append-only execution lifecycle
  -> broker and reconciliation
```

This first implementation stage is research-only. It defines strategy-target
contracts, immutable artifacts, native target backtests, and a legacy
equivalence investigation. It does not change paper, dry-run, Alpaca, scheduler,
or runtime behavior.

## Strategy Targets

A strategy target describes desired exposure, not an order. A signed share
target has direct position meaning:

```text
-10 shares = short ten shares
  0 shares = flat
+10 shares = long ten shares
```

`StrategyTargetFrame` stores timestamp-aligned decimal research targets.
Fractional shares are valid in research. Operational whole-share validation is
separate and rejects fractional targets without rounding.

`StrategyTargetDecision` is an immutable target revision. It records strategy,
input-data, sizing-policy, effective-time, validity, and source-evidence
identity. A target's declared status is either `active` or `unavailable`.

Time-derived status is evaluated without rewriting the original decision:

```text
active
not_yet_effective
expired
stale
unavailable
```

`StrategyEvaluation` is a separate observation. A `no_change` evaluation
references the effective target decision and does not create a new revision.

## Immutable Research Artifacts

Research target artifacts are stored under:

```text
data/research/strategy-targets/
data/research/strategy-evaluations/
data/research/legacy-equivalence/
```

Artifacts are schema-versioned and written exclusively. Reusing an existing ID
fails instead of overwriting history. These artifacts are research evidence;
they never authorize operational execution.

## Native And Legacy Strategies

Native target strategies emit target frames directly. Price and feature target
strategies have separate protocols, matching the existing strategy boundaries.

Existing entry/exit strategies remain unchanged. Compatibility policies convert
their event signals into resolved targets:

- `fixed_shares_v1` carries an explicit share target between entry and exit.
- `legacy_available_cash_v1` investigates current VectorBT signal behavior by
  resolving its actual orders into a target history.

Legacy equivalence is evidence, not an assumption. Baseline signal simulation
and target-amount simulation are compared across trades and portfolio metrics.
If they differ, the existing legacy simulator remains authoritative and the
result is labeled non-equivalent.

## Future Stages

Later reviewed stages will add versioned contributor ownership, deterministic
portfolio aggregation, risk targets, atomic execution-plan claims, append-only
execution events, restart recovery, reconciliation-confirmed satisfaction, and
detect-only drift. Alpaca paper integration requires a separate review.
