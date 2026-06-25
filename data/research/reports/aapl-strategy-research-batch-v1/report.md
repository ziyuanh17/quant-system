# AAPL Strategy Research Batch v1 Report

Generated from the fixed research batch artifact:

```text
data/research/strategy-batches/aapl-strategy-research-batch-v1/
```

This is a research-only report. It does not authorize dry-run, paper trading,
Alpaca, scheduler activation, broker access, orders, or fills.

## Inputs

- Market bars:
  `data/normalized/market_bars/AAPL.csv`
- Market bars SHA-256:
  `b21ba6ad44dcb408e8937f984d280f82a6d9c2e2a992f9a1cd69e6b8ed3720a2`
- Features:
  `data/features/technical/AAPL.csv`
- Features SHA-256:
  `fe9895a8bc2e3ec6909b49c577ddfd8c6c64427ae728577b824635a80e7d4c55`
- Rows:
  `1006`
- Batch artifact SHA-256:
  `96bdb6874d12bd46c7df11e5e342e220c34e6e46ea3ce19f642a0dec93c4d023`

## Evaluation Policy

The first batch is not a paper-trading qualification gate. It is a research
screen that asks whether each candidate deserves more research.

A candidate may pass only if it either:

- acts as a declared control/baseline; or
- improves on a useful metric without unacceptable degradation in return,
  drawdown, turnover, or implementation clarity.

The legacy momentum baseline is the current control. Feature momentum is
expected to match it when the feature artifact correctly reproduces the same
moving-average inputs.

## Results

| Candidate | Latest Trial | Status | Total Return | Final Value | Trades | Max Drawdown | Decision |
| --- | --- | --- | ---: | ---: | ---: | ---: | --- |
| `aapl-momentum-baseline-5-20-v1` | `trial-v2` | succeeded | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | Pass as control |
| `aapl-feature-momentum-baseline-5-20-v1` | `trial-v2` | succeeded | `1.227483` | `222748.28` | `25` | `-0.21010632998879852` | Pass for parity |
| `aapl-target-native-trend-5-20-v1` | `trial-v2` | succeeded | `0.000873` | `100087.34` | `50` | `-0.00041419746904647337` | Fail promotion |
| `aapl-vol-adjusted-trend-5-20-20-v1` | `trial-v2` | succeeded | `0.000673` | `100067.25` | `247` | `-0.00043478379509664933` | Fail promotion |
| `aapl-mean-reversion-counterweight-5-20-v1` | `trial-v2` | succeeded | `-0.000967` | `99903.32` | `43` | `-0.0011619116433893018` | Fail promotion |

## Decisions

### `aapl-momentum-baseline-5-20-v1`

Decision: **Pass as control.**

Reason: This candidate is the legacy price-momentum control. It provides the
baseline that later target-native candidates must beat or justify trading off
against.

### `aapl-feature-momentum-baseline-5-20-v1`

Decision: **Pass for parity.**

Reason: It exactly matched the price-momentum baseline on return, final value,
trade count, and max drawdown. That is useful evidence that the feature
artifact path reproduces the legacy strategy on this input.

### `aapl-target-native-trend-5-20-v1`

Decision: **Fail promotion.**

Reason: It produced much lower return than the baseline. The drawdown is very
small, but the strategy does not yet justify promotion. It may remain useful as
a semantic-target mechanics test because it produced signed target histories,
long/short transitions, and target-order backtest evidence.

### `aapl-vol-adjusted-trend-5-20-20-v1`

Decision: **Fail promotion.**

Reason: It produced much lower return than the baseline and far higher turnover
than the fixed target-native trend candidate. The volatility scaling needs
redesign before more serious evaluation.

### `aapl-mean-reversion-counterweight-5-20-v1`

Decision: **Fail promotion.**

Reason: It lost money in this batch. It may still be useful later as a
portfolio-construction counterweight, but it does not pass as a standalone
candidate.

## Evidence Artifacts

Latest backtest summaries:

```text
data/research/evaluations/aapl-momentum-baseline-5-20-v1/8670f61428f771ca3278502fc0db46aaf5d1fdddbcb0f28364446aee15b45d62/backtests/aapl-momentum-baseline-5-20-v1-trial-v2/summary.json
data/research/evaluations/aapl-feature-momentum-baseline-5-20-v1/34d23c2e4fea5590849b99c14ef3bd7e38c5afe8fa671bb1a59dd3abe6a0b431/backtests/aapl-feature-momentum-baseline-5-20-v1-trial-v2/summary.json
data/research/evaluations/aapl-target-native-trend-5-20-v1/41adcd5fb3bbd3135da32e397f8aa28e24d2361a6e6b0ed53b764e2d4dcb8b4d/backtests/aapl-target-native-trend-5-20-v1-trial-v2/summary.json
data/research/evaluations/aapl-vol-adjusted-trend-5-20-20-v1/ee7a44a1305a71db143c1871d7c8d61a61ab7c520aea8d5a4d684c2efafe991b/backtests/aapl-vol-adjusted-trend-5-20-20-v1-trial-v2/summary.json
data/research/evaluations/aapl-mean-reversion-counterweight-5-20-v1/97dd3ad90d75a545d8ece722b13fdc3ea1c30184f2e71db163a1bb7e59c711f7/backtests/aapl-mean-reversion-counterweight-5-20-v1-trial-v2/summary.json
```

Target-native candidates also persist `targets.csv` under their `trial-v2`
backtest directories.

## Next Research Step

Do not promote any candidate to dry-run, paper, Alpaca, scheduler, broker, or
order paths from this report.

Strategy-declared sizing is part of the strategy and remains the primary
comparison policy. A strategy that deliberately requests a specific share
amount should be evaluated with that requested amount unless a later portfolio
or risk stage explicitly changes it and records why.

The fixed-share batch is therefore only a secondary sizing ablation. It asks
whether the direction and timing logic still looks useful after sizing has
been neutralized. It does not replace the declared-policy comparison and
cannot promote a candidate by itself.

The next research step should improve target-native strategy design and sizing
under declared-policy evaluation, then use ablations only as supporting
diagnostics.
