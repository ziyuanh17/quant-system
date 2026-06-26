# AAPL Strategy Research Batch v2 Report

Generated: 2026-06-25T12:00:00Z

This is a research-only report. It does not authorize dry-run, paper trading,
Alpaca, broker access, scheduler use, runtime mutation, order submission, or
fills.

Batch artifact:

```text
data/research/strategy-batches/aapl-strategy-research-batch-v2/
```

Evaluation root:

```text
data/research/evaluations-v2/
```

## Summary

Batch v2 preserves the reported v1 candidates and adds one declared-policy
target-native strategy:

```text
aapl-declared-notional-trend-5-20-100k-v1
```

The new candidate declares `+100000` or `-100000` target notional exposure and
resolves that strategy-owned sizing decision into signed share targets from the
current AAPL price.

## Results

| Candidate | Trial | Total Return | Final Value | Trades | Max Drawdown | Sharpe | Decision |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- |
| `aapl-momentum-baseline-5-20-v1` | `trial-v1` | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | `1.261270` | Pass as control |
| `aapl-feature-momentum-baseline-5-20-v1` | `trial-v1` | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | `1.261270` | Pass for parity |
| `aapl-target-native-trend-5-20-v1` | `trial-v1` | `0.000873` | `100087.34` | `50` | `-0.00041419746904647337` | `0.625962` | Fail promotion |
| `aapl-vol-adjusted-trend-5-20-20-v1` | `trial-v1` | `0.000673` | `100067.25` | `247` | `-0.00043478379509664933` | `0.522650` | Fail promotion |
| `aapl-mean-reversion-counterweight-5-20-v1` | `trial-v1` | `-0.000967` | `99903.32` | `43` | `-0.0011619116433893018` | `-0.835270` | Fail promotion |
| `aapl-declared-notional-trend-5-20-100k-v1` | `trial-v1` | `0.680071` | `168007.15` | `532` | `-0.2111674998627756` | `0.744340` | Fail promotion |

## Decision

The declared-notional candidate is a better target-native research result than
the one-share target candidates because it owns a meaningful sizing policy.
However, it still fails promotion from this batch:

- total return remains below the legacy momentum control;
- max drawdown is slightly worse than the control;
- trade count is much higher, indicating excessive turnover.

The candidate is useful as research evidence for strategy-owned sizing, but it
does not justify dry-run, paper, Alpaca, scheduler, runtime, broker, order, or
fill exposure.

## Next Step

Continue research-only strategy design. The next candidate should reduce
turnover while preserving declared sizing semantics, for example by adding a
trend-strength threshold, hysteresis band, or slower rebalance rule.
