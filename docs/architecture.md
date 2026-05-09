# Architecture

This repo starts as a research/backtest core and is shaped so it can later grow into
paper trading and live trading without replacing the strategy layer.

## Current Flow

```text
CSV prices
  -> data loader
  -> strategy signal generation
  -> VectorBT backtest adapter
  -> typed BacktestResult
```

## Intended Growth

```text
data providers
  -> raw storage
  -> normalized storage
  -> feature pipeline
  -> strategy engine
  -> risk engine
  -> paper/live execution
  -> broker reconciliation
  -> monitoring and reports
```

## Boundary Principle

VectorBT is a research and analytics engine. It should not own the whole application.

The application owns:

- data contracts
- strategy interfaces
- risk models
- broker/execution models
- scheduling
- audit logs

VectorBT owns:

- fast vectorized backtests
- signal portfolio simulation
- metrics and research visualization

