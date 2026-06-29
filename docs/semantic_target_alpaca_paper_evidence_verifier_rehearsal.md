# Semantic-Target Alpaca Paper Evidence Verifier Rehearsal

This rehearsal produced fake-client Alpaca paper evidence and then verified it
with the broker-free evidence verifier.

Commands run from the development workspace:

```bash
.venv/bin/quant semantic-target alpaca-paper-fake-rehearsal \
  --rehearsal-id verifier-local \
  --output-root data/semantic-target/alpaca-paper-evidence-verifier/rehearsal

.venv/bin/quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-evidence-verifier/rehearsal/requests/verifier-local-request.json
```

The fake-client rehearsal passed:

```text
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

The broker-free verifier then passed:

```text
Request: verifier-local-request
Passed: yes
Summary: verified semantic-target Alpaca paper run
Symbol: AAPL
Approved target: 2
Execution plan: execution-fake-alpaca-paper-risk-target-r1
Final status: satisfied
Events: 4
Orders: 1
Fills: 1
Snapshots: 5
Reconciliations: 1
Final position: 2
Verification created no Alpaca or execution artifacts.
```

The durable report-writing path was rehearsed separately:

```bash
.venv/bin/quant semantic-target alpaca-paper-fake-rehearsal \
  --rehearsal-id verifier-report-local \
  --output-root data/semantic-target/alpaca-paper-verification-report/rehearsal

.venv/bin/quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-verification-report/rehearsal/requests/verifier-report-local-request.json \
  --report-path data/semantic-target/alpaca-paper-verification-report/reports/verifier-report-local-verification.json
```

The written report had schema version `1`, request id
`verifier-report-local-request`, passed with zero issues, bound the request hash
`e8eb69390675660288733d6d5607e0896a538089de43521130bd15c85f26e626`, and
recorded final status `satisfied`, four lifecycle events, one order, one fill,
five snapshots, one reconciliation report, and final `AAPL +2`.

The persisted-report verifier was rehearsed with fake-client evidence:

```bash
.venv/bin/quant semantic-target alpaca-paper-fake-rehearsal \
  --rehearsal-id report-verify-local \
  --output-root data/semantic-target/alpaca-paper-report-verifier/rehearsal

.venv/bin/quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-report-verifier/rehearsal/requests/report-verify-local-request.json \
  --report-path data/semantic-target/alpaca-paper-report-verifier/reports/report-verify-local-verification.json

.venv/bin/quant semantic-target verify-alpaca-paper-report \
  --report-path data/semantic-target/alpaca-paper-report-verifier/reports/report-verify-local-verification.json
```

The final report check passed, confirmed request id
`report-verify-local-request`, final status `satisfied`, one order, one fill,
one reconciliation, and final position `2`. It created no Alpaca or execution
artifacts.

Evidence shape:

- one reviewed request artifact;
- one fake-client rehearsal report;
- one execution plan;
- four append-only lifecycle events;
- one order artifact;
- one fill artifact;
- five account snapshots;
- one passed reconciliation report.

No Alpaca credentials were sourced. No Alpaca client was constructed. No
broker API call was made. No order-capable command was run against a real
paper account. No launchd, scheduler, runtime clone, non-paper Alpaca, or
real-money path was touched.
