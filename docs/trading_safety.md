# Live Trading Safety Gates v1

This project must fail closed around real-money trading. Live Trading Safety
Gates v1 adds the first reusable guard before any live broker adapter exists.

The default mode is always:

```text
paper
```

The supported modes are:

- `paper`: local paper broker behavior only
- `dry_run`: future live-style path that must not submit real orders
- `live`: real-money mode, blocked unless every explicit gate passes

## Safety Check

Run:

```bash
quant safety check
```

The default check should pass in paper mode:

```text
Mode: paper
Allowed: True
```

Live mode fails closed unless all required gates are present:

```bash
quant safety check --trading-mode live
```

Required live gates:

- `--live-trading-enabled`
- `--live-trading-confirmation I_UNDERSTAND_LIVE_TRADING_RISK`
- `--max-order-notional` with a positive value
- `--broker-name` with a non-empty broker name

## Environment Variables

The same check can load settings from environment variables:

```bash
quant safety check --from-env
```

Supported variables:

```text
QUANT_TRADING_MODE=paper
QUANT_LIVE_TRADING_ENABLED=false
QUANT_LIVE_TRADING_CONFIRMATION=
QUANT_MAX_ORDER_NOTIONAL=
QUANT_BROKER=
```

Missing variables do not grant permission. Invalid values stop the check.

## How Future Live Code Should Use This

Any future command or adapter that can place real orders should call
`assert_trading_allowed` before constructing a live broker client or submitting
an order. That call should happen close to the entry point so failures are
visible before credentials, network calls, or account state are touched.

This milestone does not add live broker connectivity and does not place real
trades.
