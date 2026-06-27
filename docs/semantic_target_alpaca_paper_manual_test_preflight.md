# Semantic-Target Alpaca Paper Manual Test Preflight

Date: 2026-06-26

Status: Blocked before broker interaction

## Summary

This stage performed fresh preflight for the first one-request manual Alpaca
paper API test. It did not run the order-capable command.

The preflight blocked because the local time was Friday, June 26, 2026 at
21:08 PDT, outside the regular US equity session. Submitting a paper market
order outside the session could leave a queued working order that later fills
outside the observed test window, which would violate the intended
one-request, immediately observed rehearsal.

No Alpaca API call was made.

## Source And Runtime State

Source workspace:

```text
commit: 301766b
status: ## codex/semantic-paper-infra...origin/codex/semantic-paper-infra
```

Runtime clone:

```text
commit: ddc6d9e
status:
## main...origin/main [ahead 14]
?? data/semantic-target/
```

The runtime code commit contains the reviewed Alpaca paper command and
request preparer. The source-only `301766b` commit added the manual test design
document after that code.

## Scheduler And Launchd

```text
Bad request.
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

The recurring Alpaca paper scheduler was not loaded and the launchd plist was
absent.

## Clock Evidence

```text
utc=2026-06-27T04:08:20Z
local=2026-06-26T21:08:20-0700
```

This is outside regular US equity trading hours.

## Environment Presence

After sourcing runtime `.env`, the required variables were present:

```text
QUANT_ALPACA_PAPER_API_KEY=present
QUANT_ALPACA_PAPER_SECRET_KEY=present
QUANT_ALPACA_PAPER_ACCOUNT_ID=present
QUANT_ALPACA_PAPER_URL_OVERRIDE=present
QUANT_BROKER=present
QUANT_MAX_ORDER_NOTIONAL=present
```

No secret values were printed.

## Reviewed Request

Prepared request from the runtime rehearsal:

```text
/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json
```

The request had previously validated as:

```text
request_id=runtime-alpaca-paper-request
broker=alpaca-paper
symbol=AAPL
max_qty=2.0
enabled=True
output_root=/tmp/quant-runtime-alpaca-paper-request-prep/alpaca-paper-output/runtime-alpaca-paper-request
```

Its printed validity window ended at:

```text
2026-06-27T04:19:43.447991+00:00
```

The request was still inside that window during preflight, but the market
session was closed.

## Command Not Run

This order-capable command was not run:

```text
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path /tmp/quant-runtime-alpaca-paper-request-prep/alpaca-inputs/inputs/requests/runtime-alpaca-paper-request.json \
  --from-env
```

## Verdict

Blocked before broker interaction.

The block is intentional safety evidence. The next manual paper API test
should be prepared and run during a regular US equity session, with a fresh
near-term request and fresh preflight evidence immediately before the command.
