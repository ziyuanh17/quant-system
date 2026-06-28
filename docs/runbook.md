# Runbook

This runbook documents current CLI operations. The CLI commands below are the
legacy signal-oriented lane unless stated otherwise. Semantic-target execution
remains library/API driven except for the bounded dry-run and local
semantic-paper commands documented below. No semantic-target command reaches
Alpaca or a recurring scheduler. See
[current_system_status.md](current_system_status.md).

## Supervised Provider Dry-Run

Run one reviewed local assembly through one supervised dry-run cycle:

```bash
quant dry-run supervised-provider \
  --request-path reviewed/supervised-provider-request.json
```

The reviewed request fixes the output root and exact content-hashed inputs.
The command has no paper, Alpaca, broker, scheduler, runtime, mode, or
cycle-count selector. See
[supervised_provider_operator.md](supervised_provider_operator.md) and its
[actual-command rehearsal](supervised_provider_operator_rehearsal.md).

## Local Semantic Paper

Prepare a reviewed request bundle from the latest legacy momentum signal:

```bash
quant semantic-paper prepare-momentum-request \
  --request-id reviewed-momentum-request \
  --data data/normalized/market_bars/AAPL.csv \
  --symbol AAPL \
  --quantity 2
```

This command validates local market data, runs the legacy momentum signal,
translates the latest signal into a whole-share semantic target, writes the
activation and target request inputs, and stops. It does not execute local
paper, contact Alpaca, load a scheduler, or submit any broker-network order.

Run one reviewed activated semantic-target request through durable local paper:

```bash
quant semantic-paper activated-target \
  --request-path data/semantic-target/local-paper-requests/inputs/requests/reviewed-momentum-request.json
```

The command is local-only. It consumes one reviewed request artifact, hardcodes
local semantic-paper safety, writes durable paper state, order, fill,
reconciliation, lifecycle, and orchestration evidence, and exits nonzero if
activation, targets, risk, execution, or reconciliation block. It has no mode,
Alpaca, scheduler, runtime, or broker-network selector.
See the first
[local semantic-paper request rehearsal](activated_semantic_paper_operator_rehearsal.md).

Inspect the same request without writing files or consuming activation:

```bash
quant semantic-paper inspect-activated-target \
  --request-path reviewed/activated-semantic-paper-request.json
```

Run an exact finite list of independently fresh supervised-provider requests:

```bash
quant dry-run supervised-provider-finite \
  --manifest-path reviewed/finite-supervised-provider.json
```

The command stops on the first blocked request and cannot discover additional
work. See [finite_supervised_provider.md](finite_supervised_provider.md) and
its [actual-command rehearsal](finite_supervised_provider_rehearsal.md).

Run one reviewed discovery-only request:

```bash
quant dry-run supervised-provider-discover \
  --request-path reviewed/supervised-provider-discovery-request.json
```

The reviewed request fixes the discovery policy, output root, and exact
handoff-rehearsal evidence. The command may produce a finite manifest, but it
does not run that manifest. It has no recurring, paper, Alpaca, broker,
runtime, mode, output-root, or cycle-count selector. See
[supervised_provider_discovery_operator.md](supervised_provider_discovery_operator.md).

Run one reviewed discovery-to-finite-loop request:

```bash
quant dry-run supervised-provider-discover-finite \
  --request-path reviewed/supervised-provider-discovery-loop-request.json
```

The reviewed request fixes the exact discovery-only operator request and
command-rehearsal evidence. The command runs discovery first, then only the
finite manifest produced by that discovery result. It has no recurring, paper,
Alpaca, broker, runtime, mode, output-root, or cycle-count selector. See
[supervised_provider_discovery_loop_operator.md](supervised_provider_discovery_loop_operator.md).

## Local Backtest

```bash
quant backtest --strategy momentum --data data/sample_prices.csv --symbol AAPL
```

## Ingest Market Data

```bash
quant data ingest --provider yfinance --symbol AAPL --start 2024-01-01 --end 2024-02-01
```

The normalized file can then be used for a backtest:

```bash
quant backtest --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

## Validate Market Data

```bash
quant data validate --data data/normalized/market_bars/AAPL.csv --symbol AAPL
```

Validation failures return a nonzero exit code so scheduled jobs can stop
before bad data reaches a strategy.

Ingestion and backtesting run this validation by default. Use
`--skip-validation` only when intentionally inspecting bad data behavior.

Ingestion also writes JSON lineage artifacts:

```text
data/validation/market_bars/AAPL.json
data/metadata/market_bars/AAPL.json
```

## Run A Scheduled Paper Task

```bash
quant schedule paper-order --symbol AAPL --side buy --quantity 1 --price 100 --iterations 1
```

This command writes:

```text
data/paper/scheduled/
data/scheduler/latest/
```

Use `--iterations` and `--interval-seconds` for a finite repeated run. Keep
finite loops as the default until the system has explicit service supervision,
idempotency, and alerting.

## Run A Scheduled Paper Signal

```bash
quant schedule paper-signal --strategy momentum --data data/sample_prices.csv --symbol AAPL --quantity 1 --iterations 1
```

This generates the latest strategy signal from the input data, turns that
signal into a paper-trading decision, and writes:

```text
data/paper/signals/
data/paper/state/default.json
data/scheduler/latest/
```

Use `--state-path` to isolate separate paper accounts or experiments.
If the same actionable signal is processed again, the command records a skipped
signal instead of placing a duplicate paper order.

## Refresh Data Then Run Paper Signal

```bash
quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
```

This refreshes market data, writes validation and metadata artifacts, stops if
validation fails, then runs the scheduled paper-signal path. It writes a
workflow record under:

```text
data/workflows/paper-signal-refresh/
```

Use this path for recurring server runs once the provider and start date are
configured.

## Refresh Data Then Run Dry-Run Signal

```bash
quant workflow dry-run-refresh --symbol AAPL --start 2024-01-01 --quantity 1
```

This refreshes market data, writes validation and metadata artifacts, stops if
validation fails, then runs the scheduled dry-run signal path. When paper signal
records exist, it compares the latest paper decision with the latest dry-run
intended order and writes:

```text
data/dry_run/comparison/latest.json
```

It writes its workflow record under:

```text
data/workflows/dry-run-refresh/
```

Add `--publish-status-path site/status.json` when the run should refresh the
static dashboard health payload.

## Inspect A Reviewed Activated Semantic-Target Dry-Run Request

Before running a reviewed request, inspect it:

```bash
quant dry-run inspect-activated-target \
  --request-path reviewed/activated-dry-run-request.json
```

This read-only command checks the files named by the request, evaluates
authorization and target freshness at the current time, and explains the
current position, approved target, and intended order. It does not approve the
request, reserve it, consume its one-use activation, create evidence files, or
run a dry-run. A later run must repeat all safety checks because account state
and time-sensitive inputs may change after inspection.

The first actual inspection-command rehearsal is recorded in
[activated_dry_run_request_inspection_rehearsal.md](activated_dry_run_request_inspection_rehearsal.md).

## Run A Reviewed Activated Semantic-Target Dry-Run

```bash
quant dry-run activated-target \
  --request-path reviewed/activated-dry-run-request.json \
  --activation-root data/semantic-target/activation \
  --output-root data/semantic-target/dry-run
```

The schema-versioned request artifact names the exact authorization, base
rehearsal, passing activation-consumption rehearsal, contributor set, strategy
decisions, and strategy evaluations. It also embeds the reviewed risk policy,
account snapshot, execution policy, reference price, identifiers, and
evaluation time.

The command preserves an immutable copy of the request, revalidates and
atomically consumes activation evidence, and runs only the semantic-target
dry-run path. It has no mode or broker selector and cannot invoke local paper
or Alpaca. Blocked activation creates request and activation evidence but no
strategy, portfolio, risk, lifecycle, or dry-run workflow artifacts.

The first local synthetic command rehearsal is recorded in
[activated_dry_run_operator_rehearsal.md](activated_dry_run_operator_rehearsal.md).
In that result, `would_submit` means the system calculated and recorded the
intended order; it does not mean an order was sent to a broker.

## Run A Finite Autonomous Dry-Run List

```bash
quant dry-run autonomous-finite-loop \
  --manifest-path reviewed/finite-autonomous-dry-run.json \
  --output-root data/semantic-target/autonomous-dry-run
```

This manually started command processes only the exact request files named in
the manifest. The manifest binds the authorization and every request by
SHA-256 hash, so changed inputs are rejected before the first run. The command
stops immediately on a blocked run and exits nonzero.

There is no iterations option, request discovery, paper mode, Alpaca mode,
broker selector, launchd service, or recurring scheduler connection. Starting
the command authorizes no activity beyond the finite manifest and its bounded
deployment authorization.

## Run The Service Wrapper

```bash
bash scripts/run_paper_signal_refresh.sh
```

For the dry-run rehearsal workflow:

```bash
bash scripts/run_dry_run_refresh.sh
```

For the Alpaca paper rehearsal workflow:

```bash
bash scripts/run_alpaca_paper_refresh.sh
```

This wrapper is broker-connected and may submit an Alpaca paper order when its
strategy produces an actionable delta. A documented command is not approval to
run it.

Copy `.env.example` to `.env` to configure the wrapper. See
[deployment.md](deployment.md) for cron and systemd examples.

## Check Operational Health

```bash
quant ops health
```

The health command checks the latest scheduler run record, latest paper signal
record, persisted paper state, workflow lock, and wrapper log directory. It
returns a nonzero exit code only when the status is `failed`.

For a fuller daily check:

```bash
quant ops health --reconcile-state --initial-cash 100000
```

After running paper and dry-run paths, include the comparison report:

```bash
quant ops health --check-comparison
```

See [operations.md](operations.md) for status meanings and current limits.

## Publish Dashboard Status

```bash
quant ops publish-status --initial-cash 100000
```

This writes a sanitized `site/status.json` file for the GitHub Pages dashboard.
It does not include paper cash, positions, or order details. By default, the
command still exits successfully when health is failed so the dashboard can show
the failed state; add `--fail-on-failed` only when a wrapper should stop
instead.

## Inspect A Workflow Lock

```bash
cat data/locks/paper-signal-refresh.lock
```

The lock file should exist only while the refresh workflow is running. If it is
present after a crash, check whether a workflow process is still active before
removing it. A later run can replace the lock after the configured stale
timeout.

## Inspect Paper State

```bash
cat data/paper/state/default.json
cat data/paper/state/default.json.bak
```

Paper state saves use an atomic replace. The `.bak` file is the previous state
snapshot and is useful when debugging a bad run or interrupted process.

## Reconcile Paper State

```bash
quant paper reconcile-state --initial-cash 100000
```

This replays paper signal records and compares the expected cash, positions,
and processed signal keys against `data/paper/state/default.json`. It writes a
report under:

```text
data/paper/reconciliation/state.json
```

Use the same starting cash and optional starting position that were used when
the paper account was created.

## When Something Fails

1. Run `quant ops health` and read the issue codes.
2. Inspect the latest workflow record under `data/workflows/`.
3. If the failure mentions a lock, confirm whether another workflow is running.
4. Check the `Reconciliation:` line in `quant ops health`, or run
   `quant paper reconcile-state` for the standalone report.
5. If dry-run comparison is enabled, inspect
   `data/dry_run/comparison/latest.json`.
6. Run `quant ops publish-status --initial-cash 100000` if the GitHub Pages
   dashboard should reflect the current failure.
7. Confirm the input data has the required columns:
   `date`, `symbol`, `open`, `high`, `low`, `close`, `volume`.
8. Confirm dependencies are installed in the active environment.
9. Re-run with the smallest dataset that reproduces the issue.
10. Add a regression test before changing core accounting or signal behavior.

## Semantic-Target Alpaca Paper

Run one reviewed semantic-target request against Alpaca paper:

```bash
quant semantic-target alpaca-paper \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json \
  --from-env
```

This command is broker-connected and may submit one Alpaca paper order when
all request, safety, target, lifecycle, and reconciliation gates pass. Use it
only with a reviewed request and paper credentials in the environment. It does
not expose local-paper, dry-run, real-money, scheduler, launchd, or mode
selection. After execution it automatically runs broker-free evidence
verification against the local artifacts it produced; the command exits
nonzero if that verification fails.

Verify one completed semantic-target Alpaca paper run from local evidence:

```bash
quant semantic-target verify-alpaca-paper-run \
  --request-path data/semantic-target/alpaca-paper-requests/inputs/requests/reviewed-request.json
```

This verifier is broker-free. It reads the reviewed request, lifecycle events,
order and fill records, snapshots, and reconciliation reports, then exits
nonzero if the completed run did not satisfy the approved target exactly once.
It does not load credentials, contact Alpaca, submit orders, or write execution
artifacts.

## Semantic-Target Review

Semantic-target dry-run and local semantic paper have dedicated reviewed CLI
commands documented above. Semantic-target Alpaca paper currently has a
fake-client rehearsal command, the one-request paper command, and the
broker-free evidence verifier documented above. Review semantic-target
artifacts under the configured execution root:

```text
plans/
events/
recovery-evidence/
drift-observations/
dry-run-observations/
```

Do not manually edit lifecycle artifacts. A blocked or ambiguous event is
durable evidence and must be understood before any recovery attempt. Do not
connect the real semantic-target Alpaca paper API to a CLI, wrapper, or
scheduler without a separate review.

## Web Console

Start the private web console:

```bash
quant web serve
```

Publish operational health and knowledge index:

```bash
quant ops publish-status
quant ops publish-knowledge
```

Full runbook: [console_runbook.md](console_runbook.md)
Known limits: [console_known_limits.md](console_known_limits.md)
Security boundary: [console_security_boundary.md](console_security_boundary.md)
