# Semantic-Target Fresh Market-Session Alpaca Paper Execution

Date: 2026-06-29

Status: Completed with ambiguous broker outcome; follow-up guard added.

## Summary

One fresh reviewed semantic-target Alpaca paper request was prepared and run
during the regular US equity session from the reviewed source workspace.

The command reached the Alpaca paper broker path and exited nonzero with a
durable `ambiguous` lifecycle state. It did not produce order, fill, or
reconciliation artifacts. The post-run verifier wrote an immutable failed
verification report.

No second order attempt was made.

## Source And Runtime Context

Reviewed source workspace:

```text
workspace: /Users/mochifufu/Code/quant-system
branch: codex/semantic-paper-infra...origin/codex/semantic-paper-infra
source commit before execution: 8157b6d
```

Runtime clone was checked but not used for code execution:

```text
workspace: /Users/mochifufu/Code/quant-system-runtime
status: ## main...origin/main [ahead 20]
untracked: data/semantic-target/
```

Because runtime was not on the reviewed branch, the reviewed source workspace
was used for command execution. Runtime `.env` was sourced only for Alpaca
paper credentials. Secret values were not printed.

Credential presence:

```text
QUANT_ALPACA_PAPER_API_KEY=present
QUANT_ALPACA_PAPER_SECRET_KEY=present
QUANT_ALPACA_PAPER_ACCOUNT_ID=present
QUANT_ALPACA_PAPER_URL_OVERRIDE=absent
```

Scheduler state:

```text
Could not find service "com.quant-system.alpaca-paper-refresh" in domain for user gui: 501
installed_plist_absent=true
```

## Reviewed Request

Fresh input:

```text
data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/input/AAPL.csv
```

Local semantic-paper request:

```text
data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/local-request/inputs/requests/fresh-alpaca-paper-20260629T1926Z-source.json
```

Prepared Alpaca paper request:

```text
data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/alpaca-inputs/inputs/requests/fresh-alpaca-paper-20260629T1926Z.json
```

Request summary:

```text
symbol: AAPL
approved target: +2 shares
reference price: 20.00
max order notional: 1000.0
valid_until: 2026-06-29T19:43:47.502096+00:00
```

Broker-free inspection passed:

```text
Valid now: yes
Regular session open: yes
Paper output root: data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/alpaca-output/fresh-alpaca-paper-20260629T1926Z
```

## Readiness Evidence

Readiness report:

```text
data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/readiness/fresh-alpaca-paper-20260629T1926Z-readiness.json
```

Readiness result:

```text
Ready: yes
Regular session open: yes
Credential environment present: yes
Planned verification report: data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/verifications/fresh-alpaca-paper-20260629T1926Z-verification.json
```

Artifact hashes:

```text
665634bc2d828cd26fe9d79eb6258284acbc0d9b0e86a41cac61791a474a3301  data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/alpaca-inputs/inputs/requests/fresh-alpaca-paper-20260629T1926Z.json
59e1dda97e9ff385dd60b63fad235e6753d3c0d9b7a594d5fdd0674716183bd5  data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/readiness/fresh-alpaca-paper-20260629T1926Z-readiness.json
267d910ddc79d70e12e13a278ef7c19d171860d64a2e55d894ec39d19d4993a4  data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/verifications/fresh-alpaca-paper-20260629T1926Z-verification.json
```

## Broker-Connected Command

The command run was:

```bash
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper \
  --request-path data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/alpaca-inputs/inputs/requests/fresh-alpaca-paper-20260629T1926Z.json \
  --from-env \
  --readiness-report-path data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/readiness/fresh-alpaca-paper-20260629T1926Z-readiness.json \
  --max-readiness-age-seconds 900 \
  --verification-report-path data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/verifications/fresh-alpaca-paper-20260629T1926Z-verification.json
```

Command output:

```text
Execution plan: execution-fresh-alpaca-paper-20260629T1926Z-risk-target-r1
Readiness report: data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/readiness/fresh-alpaca-paper-20260629T1926Z-readiness.json
Status: ambiguous
Order: buy 3 AAPL
Reconciliation: not written
Evidence verification: failed
Evidence blocked because: execution lifecycle is not satisfied: ambiguous
Evidence blocked because: expected exactly one order artifact, found 0
Evidence blocked because: expected exactly one fill artifact, found 0
Evidence blocked because: expected at least one reconciliation report
Evidence blocked because: final broker snapshot position differs from risk target
Evidence report: data/semantic-target/fresh-alpaca-paper-test/20260629T1926Z/verifications/fresh-alpaca-paper-20260629T1926Z-verification.json
```

The saved verification report failed independent verification:

```text
Invalid value: Alpaca paper verification report did not pass
```

## Local Evidence

Execution events:

```text
000001: planned -> submission_pending
reason: durable submission intent recorded before broker interaction

000002: submission_pending -> ambiguous
reason: broker submission outcome is ambiguous: {"available":"1","code":40310000,"existing_qty":"1","held_for_orders":"0","message":"insufficient qty available for order (requested: 3, available: 1)","symbol":"AAPL"}
```

The first broker snapshot showed:

```text
positions:
  AAPL: -1
  F: +1
open_orders: []
```

The final broker snapshot also showed:

```text
positions:
  AAPL: -1
  F: +1
open_orders: []
```

Verification report summary:

```text
passed: false
final_status: ambiguous
order_count: 0
fill_count: 0
snapshot_count: 2
reconciliation_report_count: 0
final_position_quantity: -1
```

## Design Finding

The planned target moved the account from an existing short `AAPL=-1` to a
long target `AAPL=+2`, which produced a single `BUY 3 AAPL` order request.

That is a cross-zero reversal. The approved architecture requires reversals to
be semantically explicit: close the existing exposure and open the new exposure
as separate lifecycle concepts, even if a broker might eventually accept a
single net order. The current Alpaca paper implementation did not yet include
that split.

## Follow-Up Guard

After this evidence, the source was updated so the Alpaca paper operational
risk layer blocks cross-zero reversals before broker submission until explicit
close/open execution-plan support exists.

Regression evidence:

```text
.venv/bin/python -m pytest tests/test_target_alpaca_paper.py
9 passed
```

The new regression covers the observed condition: current paper position
`AAPL=-1`, approved target `AAPL=+2`, and no order submission.

## Verdict

This stage proved the command can reach the paper broker path and preserve
fail-closed local evidence, but it did not prove satisfied end-to-end paper
execution.

The next software infrastructure step is to keep the reversal guard and add
explicit close/open reversal lifecycle support before retrying a target that
crosses zero. A later market-session paper test should use either a same-side
or flattening target, or the future explicit reversal lifecycle.
