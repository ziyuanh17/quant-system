# Semantic-Target Alpaca Paper Readiness Preflight

This stage adds a broker-free preflight command for one reviewed
semantic-target Alpaca paper test:

```bash
quant semantic-target preflight-alpaca-paper-test \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json \
  --report-path data/semantic-target/alpaca-paper-readiness/reviewed-request-preflight.json \
  --planned-verification-report-path data/semantic-target/alpaca-paper-verifications/reviewed-request-verification.json
```

The command writes one immutable readiness report. It checks:

- reviewed request hashes and target bounds;
- request expiry;
- regular US equity session state;
- presence, but never values, of required Alpaca paper environment variables;
- whether the planned verification report path already exists.

It does not load Alpaca credentials into an `AlpacaPaperConfig`, construct an
Alpaca client, contact Alpaca, submit orders, write execution artifacts, load
launchd, or start a scheduler.

## Rehearsal

At local time Sunday, June 28, 2026 23:57 PDT, the broker-free readiness path
was rehearsed against fake-client request evidence:

```bash
.venv/bin/quant semantic-target alpaca-paper-fake-rehearsal \
  --rehearsal-id readiness-local \
  --output-root data/semantic-target/alpaca-paper-readiness/rehearsal

QUANT_ALPACA_PAPER_API_KEY=paper-key \
QUANT_ALPACA_PAPER_SECRET_KEY=paper-secret \
QUANT_ALPACA_PAPER_ACCOUNT_ID=acct-fake \
.venv/bin/quant semantic-target preflight-alpaca-paper-test \
  --request-path data/semantic-target/alpaca-paper-readiness/rehearsal/requests/readiness-local-request.json \
  --report-path data/semantic-target/alpaca-paper-readiness/reports/readiness-local-preflight.json \
  --planned-verification-report-path data/semantic-target/alpaca-paper-readiness/reports/readiness-local-verification.json
```

The preflight exited nonzero and wrote a report with:

```text
ready: false
credentials_present: true
market_session_open: false
issues: regular US equity session is closed
request_id: readiness-local-request
approved_target_quantity: 2
planned_verification_report_path: data/semantic-target/alpaca-paper-readiness/reports/readiness-local-verification.json
```

That is the desired closed-session result. It proves that the command can
distinguish missing credentials from closed-market blocking without contacting
Alpaca. Generated local `data/` artifacts were removed after the rehearsal;
this document is the durable review evidence.
