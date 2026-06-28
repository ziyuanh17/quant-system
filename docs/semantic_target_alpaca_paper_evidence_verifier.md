# Semantic-Target Alpaca Paper Evidence Verifier

This stage adds a broker-free verifier for one completed semantic-target
Alpaca paper run. It is a read-only evidence check. It does not load Alpaca
credentials, construct an Alpaca client, submit orders, refresh broker state,
start launchd, or connect the semantic-target path to a recurring scheduler.

The verifier answers one question:

```text
Did this local Alpaca paper evidence satisfy the reviewed request exactly once?
```

It reads the reviewed request and local artifacts under the request output
root:

- contributor set, strategy target decisions, portfolio target, and risk target
- execution plan and append-only lifecycle events
- local order and fill records
- local account snapshots
- reconciliation reports

The pass criteria are intentionally strict:

- request-bound input hashes still match;
- all target artifacts remain inside the allowed request scope;
- the execution lifecycle reaches `satisfied`;
- lifecycle events occur before the request validity window closes;
- the execution plan target equals the approved risk target;
- exactly one order artifact exists;
- exactly one fill artifact exists;
- at least one reconciliation report exists;
- the latest reconciliation report is `passed`;
- the latest account snapshot position equals the approved target;
- all paper evidence paths stay under the request output root.

Request expiry is not treated as a failure for completed evidence by itself.
Expiry blocks a new submission. Old evidence must remain verifiable later, so
the verifier instead checks that the recorded lifecycle events happened before
the request expired.

## CLI

```bash
quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json
```

Optionally write a durable verification report:

```bash
quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json \
  --report-path data/semantic-target/alpaca-paper-verifications/reviewed-request-verification.json
```

The command exits nonzero if any evidence check fails and prints each blocked
reason. Without `--report-path`, it writes no files. With `--report-path`, it
writes one schema-versioned verification report immutably; it still creates no
Alpaca or execution artifacts.

The order-capable `quant semantic-target alpaca-paper` command also invokes
this verifier immediately after execution. A paper run that reports
`satisfied` still fails the CLI if the durable evidence verifier fails.

## Report Contract

The report binds verification to a specific reviewed request:

```text
schema_version
report_id
request_id
request_path
request_sha256
verified_at
passed
issues
symbol
approved_target_quantity
output_root
execution_plan_id
final_status
event_count
order_count
fill_count
snapshot_count
reconciliation_report_count
final_position_quantity
summary
```

Existing reports are never overwritten. Re-running verification should use a
new report path if another observation is needed.

## Review Boundary

This implementation does not broaden the paper-trading surface. The
order-capable command remains `quant semantic-target alpaca-paper`; this
verifier only reviews the files that command or the fake-client rehearsal has
already produced.

Future stages may use this verifier before and after a tightly reviewed
one-request Alpaca paper test. It should not be used as permission to enable
scheduling, automatic drift repair, non-paper Alpaca behavior, or real-money
trading.
