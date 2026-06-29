# Semantic-Target Alpaca Paper Readiness Freshness

This stage tightens the one-request semantic-target Alpaca paper command by
treating a readiness report as time-limited evidence.

The readiness report still proves only local facts:

- the reviewed request file matched its recorded hash;
- the request was valid at preflight time;
- the regular US equity session was open at preflight time;
- required Alpaca paper environment variables were present;
- the planned post-run verification report path did not already exist.

Those facts can change. A report from earlier in the day should not silently
authorize a later paper order after the request, market session, credentials,
or intended output path may have changed.

## Command Behavior

`quant semantic-target alpaca-paper` now accepts:

```bash
--max-readiness-age-seconds 900
```

When `--readiness-report-path` is supplied, the command verifies before broker
construction that the report:

- is ready;
- has no issues;
- references the exact request path;
- matches the current request file SHA-256;
- names the same planned verification report path;
- is not from the future;
- is no older than the configured freshness window.

The default freshness window is 900 seconds. A non-positive freshness value is
rejected before broker construction.

This does not add scheduler, launchd, real-money, non-paper Alpaca, automatic
drift repair, or recurring behavior. It only makes the existing one-request
paper command stricter.

## Evidence

The source-level implementation was verified on Monday, June 29, 2026 at
approximately 00:35 PDT. The market was closed, so no Alpaca API call or paper
order was attempted.

Checks run:

```text
.venv/bin/ruff check src/quant/cli.py src/quant/workflows/semantic_target_alpaca_paper_rehearsal.py tests/test_semantic_target_alpaca_paper_cli.py
All checks passed!

.venv/bin/python -m pytest tests/test_semantic_target_alpaca_paper_cli.py
19 passed in 0.66s

.venv/bin/pyright
0 errors, 0 warnings, 0 informations

.venv/bin/ruff check .
All checks passed!

.venv/bin/python -m pytest --ignore=tests/test_web_security.py --ignore=tests/test_web_console.py --ignore=tests/test_web_api.py --ignore=tests/test_web_docs_index.py
617 passed, 1 warning in 108.58s
```

The focused test suite proves:

- a matching fresh readiness report can be consumed with an injected fake
  Alpaca paper client;
- a mismatched planned verification path blocks before broker construction;
- a stale readiness report blocks before broker construction;
- an invalid max-age value blocks before broker construction;
- existing collision and closed-session guards still block before broker
  construction.

The warning in the broader non-web suite was the existing
`websockets.legacy` deprecation warning from the optional Alpaca SDK import
smoke test.
