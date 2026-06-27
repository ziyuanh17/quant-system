# Semantic-Target Alpaca Paper CLI

Date: 2026-06-26

Status: In review

## Summary

This stage implements the source command:

```bash
quant semantic-target alpaca-paper \
  --request-path <reviewed-request.json> \
  --from-env
```

The command is the first real Alpaca paper operator surface for semantic
targets. It is still one-request only. It does not add launchd, recurring
scheduling, autonomous repeated paper trading, strategy research, market-data
fetching through Alpaca, non-paper Alpaca behavior, or real-money trading.

No real Alpaca API call was made in this stage. Verification used an injected
fake paper broker client.

## Implementation

The command requires `--from-env`; this prevents a request file from carrying
secrets and makes the operator explicitly choose the environment-backed paper
account configuration.

The CLI delegates to
`run_semantic_target_alpaca_paper_operator_request`, which performs local
preflight before broker use:

- load and validate one schema-versioned reviewed request;
- reject expired requests using the new `valid_until` field;
- verify all recorded artifact hashes;
- load contributor, strategy, portfolio, and risk target artifacts;
- verify the requested symbol and maximum quantity scope;
- reject fractional operational share targets without rounding;
- preserve the request under the request-scoped output root;
- run the existing restart-safe semantic-target Alpaca paper executor.

The executor remains responsible for atomic execution-plan claiming,
working-order blocking, deterministic client order IDs, broker recovery,
append-only lifecycle events, reconciliation, and satisfaction.

## Evidence

Focused source verification:

```text
.venv/bin/python -m pytest \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_semantic_target_alpaca_paper_rehearsal.py \
  tests/test_target_alpaca_paper.py
```

Result:

```text
15 passed
```

Static checks:

```text
.venv/bin/ruff check \
  src/quant/cli.py \
  src/quant/models/operator.py \
  src/quant/workflows/semantic_target_alpaca_paper_rehearsal.py \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_semantic_target_alpaca_paper_rehearsal.py
```

Result:

```text
All checks passed!
```

```text
.venv/bin/pyright \
  src/quant/cli.py \
  src/quant/models/operator.py \
  src/quant/workflows/semantic_target_alpaca_paper_rehearsal.py \
  tests/test_semantic_target_alpaca_paper_cli.py \
  tests/test_semantic_target_alpaca_paper_rehearsal.py
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
586 passed, 1 warning
```

## Test Coverage Added

The command is tested with a fake paper broker client injected in place of the
real Alpaca adapter. The test proves:

- the reviewed request can drive the command;
- environment configuration is required;
- the run reaches `satisfied`;
- exactly one durable order file is written;
- exactly one fake fill is produced;
- reconciliation passes;
- the fake rehearsal command remains fake-client-only.

## Not Performed

This stage did not:

- source real Alpaca credentials;
- call Alpaca;
- submit a paper order;
- inspect a real broker account;
- modify the runtime clone;
- load or change launchd;
- add a scheduler;
- open a pull request.

## Next Review Gate

Review this source command and its fake-client evidence. The next stage should
be a manual runtime paper-run rehearsal design or an explicitly approved manual
paper run using one reviewed request. That stage must record fresh evidence of
the scheduler-unloaded state and runtime-clone status before any paper API
interaction.
