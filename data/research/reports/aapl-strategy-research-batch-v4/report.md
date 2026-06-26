# AAPL Strategy Research Batch v4 Report

Generated: 2026-06-25T22:00:00Z

This is a research-only report. It does not authorize dry-run, paper trading,
Alpaca, broker access, scheduler use, runtime mutation, order submission, or
fills.

Batch artifact:

```text
data/research/strategy-batches/aapl-strategy-research-batch-v4/
```

Evaluation root:

```text
data/research/evaluations-v4/
```

## Summary

Batch v4 preserves the reported v3 candidates and adds one declared-policy
target-native strategy:

```text
aapl-rebalance-band-notional-trend-5-20-100k-5pct-v1
```

The new candidate keeps target notional exposure inside the strategy, then
avoids daily resizing unless the signed share target has drifted by at least
`5%` from the currently held target. This preserves the strategy's sizing
decision while reducing turnover caused by small price-to-share recalculations.

## Results

| Candidate | Trial | Total Return | Final Value | Trades | Max Drawdown | Sharpe | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `aapl-momentum-baseline-5-20-v1` | `trial-v1` | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | `1.261270` | Pass as control |
| `aapl-feature-momentum-baseline-5-20-v1` | `trial-v1` | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | `1.261270` | Pass for parity |
| `aapl-target-native-trend-5-20-v1` | `trial-v1` | `0.000873` | `100087.34` | `50` | `-0.00041419746904647337` | `0.625962` | Fail promotion |
| `aapl-vol-adjusted-trend-5-20-20-v1` | `trial-v1` | `0.000673` | `100067.25` | `247` | `-0.00043478379509664933` | `0.522650` | Fail promotion |
| `aapl-mean-reversion-counterweight-5-20-v1` | `trial-v1` | `-0.000967` | `99903.32` | `43` | `-0.0011619116433893018` | `-0.835270` | Fail promotion |
| `aapl-declared-notional-trend-5-20-100k-v1` | `trial-v1` | `0.680071` | `168007.15` | `532` | `-0.2111674998627756` | `0.744340` | Fail promotion |
| `aapl-hysteresis-notional-trend-5-20-100k-v1` | `trial-v1` | `0.418560` | `141856.03` | `488` | `-0.23307565652185935` | `0.567468` | Fail promotion |
| `aapl-rebalance-band-notional-trend-5-20-100k-5pct-v1` | `trial-v1` | `0.709748` | `170974.83` | `101` | `-0.2087666409999036` | `0.767985` | Promising, fail operational promotion |

## Decision

The rebalance-band notional candidate is the strongest target-native result so
far. Compared with the v2 declared-notional candidate, it raises total return
from `0.680071` to `0.709748`, reduces trades from `532` to `101`, improves max
drawdown from `-0.2111674998627756` to `-0.2087666409999036`, and improves
Sharpe from `0.744340` to `0.767985`.

It still fails operational promotion because it trails the legacy momentum
control on total return and Sharpe, and its trade count remains higher than the
control's `25` trades. The result is promising research evidence for
rebalance-band target semantics, not authorization for dry-run, paper, Alpaca,
scheduler, runtime, broker, order, or fill exposure.

## Next Step

Continue research-only refinement around the rebalance-band candidate. The next
step should evaluate whether the same idea is robust under a small frozen grid
of rebalance thresholds and trend windows, with every attempted variant
persisted as evidence.
