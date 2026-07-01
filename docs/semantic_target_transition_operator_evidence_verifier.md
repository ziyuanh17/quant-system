# Semantic-Target Transition Operator Evidence Verifier

This stage adds a read-only verifier for local semantic-paper transition
operator evidence.

It does not execute a strategy, submit an order, contact Alpaca, read broker
credentials, alter runtime-clone state, or expose a scheduler. It only reads
local artifacts produced by:

```text
quant semantic-paper transition-target
```

## Commands

Verify local evidence directly:

```text
quant semantic-paper verify-transition-target \
  --request-path reviewed-local-paper-request.json \
  --output-root data/semantic-target/local-paper-transition
```

Optionally persist an immutable report:

```text
quant semantic-paper verify-transition-target \
  --request-path reviewed-local-paper-request.json \
  --output-root data/semantic-target/local-paper-transition \
  --report-path reports/transition-verification.json
```

Verify a persisted report:

```text
quant semantic-paper verify-transition-report \
  --report-path reports/transition-verification.json
```

## Verified Contract

The verifier passes only when:

- the reviewed request still matches the preserved operator request;
- the request's activation-consumption rehearsal evidence still matches the
  passing base rehearsal;
- the execution plan exists and is `satisfied`;
- the transition plan exists;
- every transition leg is `reconciled`;
- order count equals transition-leg count;
- fill count equals transition-leg count;
- reconciliation report count equals transition-leg count;
- every reconciliation report passed;
- the latest local paper snapshot position equals the approved risk target.

The persisted report binds to:

- request path;
- request SHA-256;
- output root;
- execution plan ID;
- transition plan ID;
- leg/order/fill/snapshot/reconciliation counts;
- final local paper position.

If the reviewed request changes after the report is written,
`verify-transition-report` fails before the report can be reused.

## Verification

Focused checks:

```text
.venv/bin/python -m pytest tests/test_activated_semantic_paper_cli.py tests/test_semantic_paper.py
20 passed

.venv/bin/ruff check src/quant/cli.py src/quant/workflows/activated_dry_run_operator.py src/quant/workflows/__init__.py src/quant/models/operator.py src/quant/models/__init__.py tests/test_activated_semantic_paper_cli.py
All checks passed!
```

The tests prove:

- a reviewed local transition run can be verified into a passing report;
- the report records two reconciled legs, two orders, two fills, two
  reconciliations, and final `AAPL=3`;
- the persisted report verifier accepts the untouched report;
- tampering with the reviewed request after report creation blocks report
  verification.

## Remaining Boundary

This remains local paper only. The next stage should use the verified report as
the handoff artifact for a runtime-clone command rehearsal, still without
Alpaca reversal exposure or recurring scheduler activation.
