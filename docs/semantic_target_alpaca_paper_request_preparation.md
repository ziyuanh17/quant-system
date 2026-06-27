# Semantic-Target Alpaca Paper Request Preparation

Date: 2026-06-26

Status: In review

## Summary

This stage implements a broker-free request preparer:

```bash
quant semantic-target prepare-alpaca-paper-request \
  --request-id <safe-id> \
  --source-request-path <reviewed-local-semantic-paper-request.json> \
  --output-root <prepared-input-root> \
  --paper-output-root <future-paper-evidence-root> \
  --max-order-notional <reviewed-notional> \
  --allowed-max-quantity <reviewed-quantity> \
  --valid-for-seconds <seconds>
```

The command prepares one `SemanticTargetAlpacaPaperOperatorRequest` from an
existing reviewed local semantic-paper request. It does not source
credentials, construct an Alpaca client, contact Alpaca, inspect broker state,
submit orders, run local paper, run dry-run, load launchd, or run a scheduler.

## Implementation

The new workflow function
`prepare_semantic_target_alpaca_paper_request`:

- loads one `ActivatedSemanticPaperOperatorRequest`;
- copies its contributor, strategy target, and strategy evaluation artifacts by
  content;
- aggregates portfolio target artifacts deterministically;
- evaluates the risk target deterministically;
- rejects blocked portfolio targets;
- rejects rejected risk targets;
- rejects fractional operational targets without rounding;
- rejects approved targets above the reviewed quantity bound;
- rejects target notional above the reviewed notional bound;
- writes one schema-versioned Alpaca paper operator request with hashes for all
  required target artifacts.

The generated request uses a live-shaped Alpaca paper safety config:

```text
mode = live
broker_name = alpaca-paper
live_trading_enabled = true
live_trading_confirmation = I_UNDERSTAND_LIVE_TRADING_RISK
max_order_notional = reviewed CLI value
```

The `live` mode here is the existing broker-connected paper safety gate. It
does not authorize real-money trading.

## CLI Output

The command prints the request path, source request path, symbol, approved
target, reference price, max order notional, validity window, and future paper
output root.

It always ends with:

```text
Prepared only. No Alpaca API call was made.
```

## Evidence

Focused tests:

```text
.venv/bin/python -m pytest \
  tests/test_semantic_target_alpaca_paper_request_cli.py \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_semantic_target_alpaca_paper_rehearsal.py \
  tests/test_semantic_paper_request_cli.py \
  tests/test_docs_index.py
```

Result:

```text
40 passed
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
589 passed, 1 warning
```

## Test Coverage Added

The new test file proves:

- a generated local semantic-paper request can be converted into an Alpaca
  paper request;
- the prepared request has Alpaca paper safety settings;
- portfolio and risk target files are written;
- the approved quantity bound is enforced;
- rerunning the same preparation command reuses the same reviewed request path;
- help text describes preparation only and does not mention scheduler or
  credentials.

## Not Performed

This stage did not:

- source `.env`;
- read or print Alpaca credentials;
- construct `AlpacaPaperBrokerClient`;
- contact Alpaca;
- inspect a paper account;
- submit a paper order;
- modify the runtime clone;
- load launchd;
- add or run a scheduler;
- open a pull request.

## Next Gate

The next stage should fast-forward or verify the runtime clone, run the
preparer there with synthetic/local reviewed inputs, and prove it writes one
reviewed request without credentials or broker access. Only after that
runtime preparation rehearsal should the project proceed to one manual Alpaca
paper API test.
