# Contributing

This is currently a solo project, but the workflow should still be boring and
repeatable.

## Local Setup

```bash
make install
```

## Before Pushing

```bash
make check
```

## Backtest Smoke Test

```bash
make backtest
```

## Code Shape

Keep dictionaries at the edges. Core modules should use typed Pydantic models
or explicit pandas objects with typed wrappers.
