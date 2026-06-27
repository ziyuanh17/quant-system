# Semantic-Target Alpaca Paper Market Session Guard

Date: 2026-06-27

Status: In review

## Summary

This stage hardens the order-capable command:

```bash
quant semantic-target alpaca-paper
```

The command now refuses to run when the regular US equity session is closed.
The check runs before Alpaca paper credentials are loaded and before the
`AlpacaPaperBrokerClient` is constructed.

This prevents an out-of-session paper market order from being queued and later
filling outside the observed rehearsal window.

## Implementation

The CLI now checks `_is_regular_us_equity_session(_current_utc())` before it
loads Alpaca paper configuration.

The session helper uses:

- `America/New_York` time;
- regular session window `09:30` to `16:00`;
- weekdays only;
- common US equity holidays;
- early closes at `13:00` for common half-day sessions.

If the session is closed, the command exits before broker construction with:

```text
regular US equity session is closed; refusing to submit or queue an Alpaca paper market order
```

## Evidence

Focused tests:

```text
.venv/bin/python -m pytest \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_semantic_target_alpaca_paper_request_cli.py \
  tests/test_semantic_target_alpaca_paper_rehearsal.py \
  tests/test_docs_index.py
```

Result:

```text
40 passed
```

Static checks:

```text
.venv/bin/ruff check src/quant/cli.py tests/test_semantic_target_alpaca_paper_cli.py
```

Result:

```text
All checks passed!
```

```text
.venv/bin/pyright src/quant/cli.py tests/test_semantic_target_alpaca_paper_cli.py
```

Result:

```text
0 errors, 0 warnings, 0 informations
```

Full non-web regression suite:

```text
.venv/bin/python -m pytest --ignore=tests/test_web_security.py
```

Result:

```text
591 passed, 1 warning
```

## Test Coverage Added

The tests prove:

- the order-capable command can still run with an injected fake paper client
  when the session predicate is open;
- the command blocks when the session predicate is closed;
- no environment variables are required for the closed-session block;
- the calendar helper returns open for a regular Monday session;
- the calendar helper returns closed for a Saturday;
- the calendar helper returns closed for Christmas.

## Not Performed

This stage did not:

- source `.env`;
- construct a real Alpaca paper client;
- contact Alpaca;
- submit a paper order;
- modify the runtime clone;
- load launchd;
- run a scheduler.

## Next Gate

The next manual paper preflight should be rerun during a regular US equity
session with a fresh near-term request. The command now has a source-level
guard against the closed-session condition observed in the previous preflight.
