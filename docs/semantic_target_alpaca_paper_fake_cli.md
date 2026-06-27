# Semantic-Target Alpaca Paper Fake CLI

This document records the first CLI-level fake-client rehearsal for the
semantic-target Alpaca paper operator boundary.

The command uses `FakeLiveBrokerClient`, not real Alpaca. It creates reviewed
target artifacts, a schema-versioned request, and durable execution evidence
under the selected output root. It does not source `.env`, use credentials,
contact Alpaca, load launchd, run a scheduler, or submit broker-network
orders.

## Command

```bash
.venv/bin/quant semantic-target alpaca-paper-fake-rehearsal \
  --rehearsal-id semantic-target-alpaca-paper-fake-cli \
  --output-root /tmp/quant-semantic-target-alpaca-paper-fake-cli-20260626
```

## Result

The command reported:

```text
Report: /tmp/quant-semantic-target-alpaca-paper-fake-cli-20260626/reports/semantic-target-alpaca-paper-fake-cli.json
Passed: yes
First status: satisfied
Second status: satisfied
Execution plan: execution-fake-alpaca-paper-risk-target-r1
Orders: 1
Fills: 1
Final position: 2
Reconciliations: 1
Evidence files: 18
```

The generated report and request hashes were:

```text
ee77d647d832573ef5c690b98d895de7b1ba0cac7d9b2b147259a1e55bb16606  /tmp/quant-semantic-target-alpaca-paper-fake-cli-20260626/reports/semantic-target-alpaca-paper-fake-cli.json
9fa0da4f7bbb47e400fa6ca32895d2a09f8361080b5db36aa41f6d35b3c3dde3  /tmp/quant-semantic-target-alpaca-paper-fake-cli-20260626/requests/semantic-target-alpaca-paper-fake-cli-request.json
```

## Interpretation

The CLI now exposes a dedicated fake-client operator boundary for the
semantic-target Alpaca paper path. This proves the command surface, reviewed
request model, durable evidence, reconciliation-confirmed satisfaction, and
restart reuse before any real Alpaca paper API use.

This rehearsal does not authorize real Alpaca paper API use, recurring
scheduling, launchd, non-paper Alpaca behavior, or real-money trading.

