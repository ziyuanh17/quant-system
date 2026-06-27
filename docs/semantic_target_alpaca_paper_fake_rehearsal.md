# Semantic-Target Alpaca Paper Fake-Client Rehearsal

This document records the source-level fake-client rehearsal for the
semantic-target Alpaca paper testing boundary.

The rehearsal used `FakeLiveBrokerClient`, not real Alpaca. It wrote reviewed
target artifacts, a reviewed Alpaca paper operator request, durable execution
evidence, and a verified report under `/tmp`. It did not source `.env`, use
credentials, contact Alpaca, load launchd, run a scheduler, or submit a
broker-network order.

## Scope

- Rehearsal root:
  `/tmp/quant-semantic-target-alpaca-paper-fake-rehearsal-20260626`
- Rehearsal ID: `semantic-target-alpaca-paper-fake`
- Request ID: `semantic-target-alpaca-paper-fake-request`
- Broker client: `FakeLiveBrokerClient`
- Broker name: `alpaca-paper`
- Broker environment: `paper`
- Target: `AAPL +2`
- Reference price: `100`
- Max order notional: `1000`

## Result

The verified report recorded:

- passed: `True`
- first status: `satisfied`
- second status: `satisfied`
- durable order count: `1`
- fill count: `1`
- final position quantity: `2`
- reconciliation report count: `1`
- evidence file count: `18`
- prohibited API calls: none

The second execution reused the existing satisfied execution plan and did not
create a duplicate order or fill.

## Key Artifact Hashes

```text
15887ea618f9882aa4f7768940bfce75aa0f4c27b946324989986c2345126706  /tmp/quant-semantic-target-alpaca-paper-fake-rehearsal-20260626/reports/semantic-target-alpaca-paper-fake.json
c3ef227a7c36da9271b3dfca914a7b5cca21b70f8f6de865127fb438df6fb43e  /tmp/quant-semantic-target-alpaca-paper-fake-rehearsal-20260626/requests/semantic-target-alpaca-paper-fake-request.json
3f080fcee1a881f7bc5e77a1392319dbf17dd143c80d27ca3f10947be5d52dc0  /tmp/quant-semantic-target-alpaca-paper-fake-rehearsal-20260626/output/orders/4350c11f-52cd-48f0-ba18-c106a7a507ab.json
b8f625724b8f7212436243405f608fd6afafd70fc9e5aadd68e9fbe4a5c0f26d  /tmp/quant-semantic-target-alpaca-paper-fake-rehearsal-20260626/output/fills/a7cd32bd-2a47-452d-9c00-ac2f1994af1e.json
```

## Source Verification

The focused source checks passed:

```text
Ruff: passed
Pyright: 0 errors, 0 warnings
tests/test_semantic_target_alpaca_paper_rehearsal.py: passed
tests/test_target_alpaca_paper.py: passed
```

## Interpretation

The source now has a schema-versioned reviewed request model and a fake-client
rehearsal for the semantic-target Alpaca paper path. This proves the local
software lifecycle can bind reviewed target artifacts, enforce the explicit
Alpaca paper submission gate, execute through the existing live-shaped paper
adapter path, reconcile satisfaction, and avoid duplicate submission on
restart.

This rehearsal does not authorize real Alpaca paper API use, recurring
scheduling, launchd, real-money trading, or non-paper Alpaca behavior.

