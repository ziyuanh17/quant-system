# Code Style

## Typed Core Rule

No untyped dictionaries in core domain logic.

A dictionary crossing a module boundary must be one of:

- parsed immediately into a Pydantic model
- annotated as a `TypedDict`
- confined to config, logging, or external API glue code

## Preferred Types

Use Pydantic models for data entering or leaving the system.

Use frozen dataclasses only for trusted internal objects that do not need validation.

Use `TypedDict` only when an external API or library forces dict-shaped data.

## Strategy Interfaces

Prefer this:

```python
def generate_signals(data: PriceData) -> SignalFrame:
    ...
```

Avoid this:

```python
def generate_signals(data: dict) -> dict:
    ...
```

