# AAPL Strategy Research Batch v3 Report

Generated: 2026-06-25T20:30:00Z

This is a research-only report. It does not authorize dry-run, paper trading,
Alpaca, broker access, scheduler use, runtime mutation, order submission, or
fills.

Batch artifact:

```text
data/research/strategy-batches/aapl-strategy-research-batch-v3/
```

Evaluation root:

```text
data/research/evaluations-v3/
```

## Summary

Batch v3 preserves the reported v2 candidates and adds one declared-policy
target-native strategy:

```text
aapl-hysteresis-notional-trend-5-20-100k-v1
```

The new candidate keeps target notional exposure inside the strategy, then adds
entry and exit bands around the moving-average spread. The design intent is to
avoid flipping exposure on small signal changes while preserving signed,
strategy-owned target sizing.

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

## Decision

The hysteresis-notional candidate confirms that a simple entry/exit band can
reduce declared-notional turnover, but the improvement is too small to justify
promotion. Compared with the v2 declared-notional candidate, it reduces trades
from `532` to `488` but also lowers total return from `0.680071` to `0.418560`,
worsens max drawdown from `-0.2111674998627756` to `-0.23307565652185935`, and
lowers Sharpe from `0.744340` to `0.567468`.

The candidate is useful negative evidence for this specific turnover-control
rule. It does not justify dry-run, paper, Alpaca, scheduler, runtime, broker,
order, or fill exposure.

## Next Step

Continue research-only strategy design. The next candidate should preserve
strategy-declared sizing while changing the signal quality or rebalance
mechanism more materially than this simple hysteresis band.
