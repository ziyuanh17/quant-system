# Semantic-Target Alpaca Paper Request Inspection

Date: 2026-06-27

Status: In review

## Summary

This stage adds a broker-free inspection command:

```bash
quant semantic-target inspect-alpaca-paper-request \
  --request-path <prepared-alpaca-paper-request.json>
```

It validates a prepared Alpaca paper request locally before the order-capable
command is considered. It does not source credentials, construct an Alpaca
client, contact Alpaca, inspect a broker account, submit orders, write
execution artifacts, load launchd, or run a scheduler.

## Implementation

The workflow function
`inspect_semantic_target_alpaca_paper_operator_request` checks:

- request schema validity;
- target artifact hashes;
- contributor, strategy, portfolio, and risk target scope;
- risk target approval;
- whole-share operational target;
- reviewed maximum quantity;
- reviewed maximum notional;
- request expiry;
- strategy decision symbol scope;
- regular US equity session state.

The command prints:

- request ID;
- valid-now result;
- summary;
- symbol;
- approved target;
- reference price;
- max quantity;
- max notional;
- validity window;
- regular-session state;
- future paper output root;
- block reasons, if any.

It always prints:

```text
Inspection created no Alpaca or execution artifacts.
```

## Evidence

Focused tests:

```text
.venv/bin/python -m pytest \
  tests/test_semantic_target_alpaca_paper_request_cli.py \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_docs_index.py
```

Result:

```text
41 passed
```

Static checks:

```text
.venv/bin/ruff check \
  src/quant/cli.py \
  src/quant/workflows/semantic_target_alpaca_paper_rehearsal.py \
  src/quant/workflows/__init__.py \
  tests/test_semantic_target_alpaca_paper_request_cli.py
```

Result:

```text
All checks passed!
```

```text
.venv/bin/pyright \
  src/quant/cli.py \
  src/quant/workflows/semantic_target_alpaca_paper_rehearsal.py \
  src/quant/workflows/__init__.py \
  tests/test_semantic_target_alpaca_paper_request_cli.py
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
595 passed, 1 warning
```

## Test Coverage Added

The tests prove:

- a prepared Alpaca paper request can inspect as ready with the regular session
  open;
- inspection blocks when the regular session is closed;
- inspection blocks when the request is expired;
- inspection help remains broker-free and does not mention credentials.

## Next Gate

The next stage should rehearse this inspector from the runtime clone against a
prepared request. After that, the first real paper API attempt should still use
a fresh near-term request and fresh market-hours preflight evidence.
