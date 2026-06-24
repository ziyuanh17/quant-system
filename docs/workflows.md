# Workflows

Workflows compose existing commands into repeatable operational paths. They are
where the system starts to behave like a server instead of a set of manual CLI
steps.

The workflows in this document are the legacy signal-oriented operational
lane. The semantic-target lifecycle is currently API-only and is not called by
these wrappers or schedulers.

The API-only controlled semantic-target orchestration persists strategy
decisions and evaluations, contributor ownership, portfolio and risk targets,
and one immutable orchestration result before or alongside semantic dry-run or
local semantic-paper evidence. It deliberately has no CLI, server wrapper,
scheduler, runtime-clone, or Alpaca entry point.

The no-network local orchestration rehearsal exercises the controlled boundary
with isolated eligible, restart, stale-target, working-order, risk-rejection,
fractional-target, and local-paper scenarios. Its immutable report verifies
that every linked orchestration record remains present and agrees with the
summary. It is an API review tool, not an operational command.

The rehearsal also injects one deterministic reconciliation failure through a
local semantic-paper-only reconciliation dependency. This proves a filled
execution remains unsatisfied across restart and does not duplicate its order
or fill. The injection is identified in the orchestration fingerprint and is
not available to Alpaca or broker-connected workflows.

The API-only semantic-target activation gate evaluates an immutable,
time-bounded authorization against the exact digest and verified evidence of a
passing local rehearsal report. It persists the authorization and every
allowed or blocked evaluation. Gate v1 supports only dry-run and local
semantic-paper scopes; Alpaca paper is explicitly unsupported. The gate does
not expose or invoke a workflow, broker adapter, CLI command, scheduler, or
runtime service.

Separate API-only activated wrappers consume an allowed evaluation for exactly
one dry-run or local semantic-paper orchestration. They immediately re-evaluate
authorization and rehearsal evidence, atomically bind the evaluation to one
orchestration, and stop before target or execution artifacts when blocked.
These wrappers remain unavailable to CLI, Alpaca, schedulers, and runtime
services.

A second-layer no-network rehearsal consumes a completed base semantic-target
rehearsal and proves activated dry-run/local-paper restart safety, durable
expired and scope-mismatch blocking, and atomic single-consumption
enforcement. Its immutable report verifies the base report digest and every
linked activation, consumption, and workflow artifact.

The activated dry-run operator boundary consumes one schema-versioned reviewed
request artifact through `quant dry-run activated-target`. It preserves the
request, verifies the exact passing activation-consumption rehearsal, hardcodes
dry-run safety, and exits nonzero for blocked activation, blocked target
stages, or a blocked dry-run observation. It exposes no mode, broker,
local-paper, Alpaca, scheduler, or runtime selector.

`quant dry-run inspect-activated-target` is the read-only companion command.
It checks and explains the request using the current time, but writes no files
and does not consume activation or run any workflow. Inspection is useful
before execution, but it is not approval and cannot guarantee that a later run
will still be valid.

The API-only autonomous dry-run workflow permits repeated broker-free runs
under one bounded deployment authorization. Every attempt is atomically
claimed and durably recorded. An expired or exceeded authorization, an
out-of-scope target, or any blocked run halts later attempts under that
authorization. No CLI, scheduler, paper, Alpaca, or broker path calls it.

The autonomous dry-run local rehearsal runs five isolated synthetic scenarios
and writes an immutable report that verifies every linked authorization, run
record, and dry-run workflow record. It remains API-only and no-network.

The finite autonomous dry-run operator command consumes one content-bound
manifest and processes only its ordered request list. It verifies all hashes
before starting, stops on the first blocked result, and writes one immutable
loop summary. It exposes no request discovery, unbounded iterations, paper,
Alpaca, broker, scheduler, or runtime selector.

The API-only supervised autonomous dry-run service obtains one fresh request
per cycle while an immutable policy remains within its cycle and runtime
bounds. It checks an explicit shutdown signal and one durable health decision
before every run. Any degraded health, blocked run, provider error, or bound
stops the service. Append-only cycle events support restart without repeating
completed cycles. No CLI, scheduler, launchd, runtime, paper, Alpaca, or broker
path calls this service.

The supervised-service no-network rehearsal runs eight isolated synthetic
scenarios and writes one immutable report linking every service record, cycle
event, health check, and autonomous run. Reopening the report verifies those
links and confirms that no order, fill, or semantic-paper directory appeared.

The API-only supervised provider adapters validate immutable health snapshots
and request envelopes. Health proceeds only when every required component is
current and healthy. Requests proceed only when source, cycle, authorization,
generation time, expiry, and maximum age all match the versioned provider
policy. Provider mismatches stop before the autonomous workflow.

The API-only local provider assembly consumes one content-bound manifest of
reviewed semantic-target artifacts. It validates every file hash and required
identity before writing one immutable health snapshot and request envelope.
Restart verifies the manifest and output hashes. It does not run the
supervisor or expose any operational path.

The provider-assembly no-network rehearsal runs seven isolated scenarios and
writes one immutable report linking inputs, legitimate assembly records,
generated provider inputs, rejection reasons, and one completed supervised
dry-run service record. Reopening the report verifies those links and rescans
the evidence tree for prohibited operational directories.

The manually started `quant dry-run supervised-provider` command consumes one
immutable reviewed request that binds the exact assembly manifest, passing
assembly rehearsal, single-cycle service policy, and evidence output root. It
assembles the provider inputs and runs one supervised dry-run cycle. It has no
recurring, deployment, paper, Alpaca, broker, or order capability.

Its separate actual-command rehearsal captures immutable executable and source
identity, arguments, exit code, stdout, and stderr for fresh completion,
restart reuse, stale-input blocking, and changed-input blocking. The verifier
reopens every linked artifact and rescans the evidence tree for operational
directories.

The manually started `quant dry-run supervised-provider-finite` command
processes only an exact content-hashed ordered request list. Every request
independently assembles fresh inputs for one supervised dry-run cycle. The
runner preflights all linked hashes, stops durably on the first block, and
cannot discover more work or continue indefinitely.

Its separate actual-command rehearsal binds executable and source identity,
captures command output for exact-list completion, restart reuse, preflight
rejection, and stop-on-block behavior, and verifies all linked loop evidence
without adding operational capability.

The API-only supervised-provider request discovery contract reads a reviewed
directory of one-cycle operator request files, verifies each file and linked
assembly artifact, and writes one exact finite manifest plus a durable
completed or blocked discovery result. It does not run the finite loop and has
no CLI, scheduler, launchd, runtime, paper, Alpaca, broker, or order path.

The discovery handoff rehearsal verifies that contract end to end without
network access. It covers successful discovery-to-loop handoff, restart reuse,
empty reviewed directories, request-limit blocks, changed linked evidence, and
finite-loop stop-on-block behavior. The report reopens all linked evidence and
checks that no operational directories were created.

The manually started `quant dry-run supervised-provider-discover` command
consumes one reviewed discovery request. It verifies the exact
discovery-handoff rehearsal, runs discovery only, writes one operator record,
and exits nonzero if discovery blocks. It may write a finite manifest but does
not run it, and exposes no scheduler, runtime, paper, Alpaca, broker, mode,
output-root, or iteration selector.

Its actual-command rehearsal captures executable and source identity, command
arguments, exit code, stdout, and stderr for fresh completion, restart reuse,
blocked discovery, and tampered rehearsal evidence. The verifier reopens every
linked artifact and confirms that no operational directories were created.

The manually started `quant dry-run supervised-provider-discover-finite`
command consumes one reviewed composition request. It verifies the
discovery-only command rehearsal, runs one reviewed discovery-only operator
request, and then runs only the exact finite manifest produced by discovery.
It writes one composition record, exits nonzero on discovery or finite-loop
blocks, and exposes no scheduler, runtime, paper, Alpaca, broker, mode,
output-root, or iteration selector.

Its actual-command rehearsal captures executable and source identity, command
arguments, exit code, stdout, and stderr for completion, restart reuse,
blocked discovery, blocked finite loop, and tampered prerequisite rehearsal
evidence. The verifier reopens every linked artifact and confirms that no
operational directories were created.

The discovery-to-loop promotion boundary is source-only. It defines the
evidence required before considering any stronger operational use of the
manual command, but it does not add a runtime path, scheduler, launchd job,
paper mode, Alpaca path, broker access, or order capability.

The source promotion review accepts that checked-in source evidence only far
enough to design a runtime-clone copy rehearsal. It does not authorize copying
source, running workflows, loading launchd, or touching broker-connected paths.

The runtime-copy rehearsal design keeps the next proposed runtime step narrow:
fast-forward reviewed source into the runtime clone, then verify package import
and command help only. It explicitly excludes request execution, credentials,
launchd, scheduler, paper, Alpaca, broker, semantic-paper, order, and fill
paths.

The first runtime-copy rehearsal attempt stopped during read-only preflight
because the runtime clone contained unrelated web-app modifications. Those
changes were preserved in a runtime-clone Git stash and the clone now reports
clean. The attempt did not fetch, merge, import, run command help, source
credentials, load launchd, run workflows, or touch broker-connected paths.

The successful retry fast-forwarded the clean runtime clone to reviewed source,
then verified package import and command help only. The runtime clone remained
clean afterward. No workflow request, `.env`, credentials, launchd, scheduler,
paper, Alpaca, broker, order, or fill path was invoked.

## Paper Signal Refresh

Run:

```bash
quant workflow paper-signal-refresh --symbol AAPL --start 2024-01-01
```

This workflow performs one ordered sequence:

```text
fetch provider data
  -> write raw data
  -> write normalized market bars
  -> write validation report and metadata
  -> stop if validation fails
  -> run scheduled paper signal
  -> write workflow record
```

The workflow record is written under:

```text
data/workflows/paper-signal-refresh/
```

It links the refreshed raw data, normalized data, validation report, metadata,
scheduler run records, paper signal records, and paper broker state path. This
linkage is the main reason the workflow exists: debugging a paper decision
should start from one record and trace back to the exact data refresh that
produced it.

## Server Wrapper

For recurring server-style runs, prefer:

```bash
bash scripts/run_paper_signal_refresh.sh
```

This wrapper loads `.env`, runs the refresh workflow, and writes a timestamped
log under `logs/`.

For recurring dry-run rehearsals, use:

```bash
bash scripts/run_dry_run_refresh.sh
```

This wrapper loads `.env`, runs `quant workflow dry-run-refresh`, writes a
timestamped log under `logs/`, and uses `QUANT_DRY_RUN_*` paths for dry-run
orders, dry-run scheduler records, comparison reports, workflow records, and
the dry-run workflow lock.

For recurring Alpaca paper rehearsals, use:

```bash
bash scripts/run_alpaca_paper_refresh.sh
```

This wrapper loads `.env`, runs `quant workflow alpaca-paper-refresh --from-env`,
writes a timestamped log under `logs/`, and uses `QUANT_ALPACA_PAPER_*` paths
for workflow records, the Alpaca paper workflow lock, live order/fill/snapshot
artifacts, and reconciliation output. It does not retry broker submission.
Set `QUANT_ALPACA_PAPER_PUBLISH_STATUS_AFTER_RUN=true` when the wrapper should
also run `quant ops publish-status --check-alpaca-paper` and refresh
`QUANT_ALPACA_PAPER_PUBLISH_STATUS_PATH`.

For a no-order configuration check, run:

```bash
QUANT_ALPACA_PAPER_PREFLIGHT_ONLY=true bash scripts/run_alpaca_paper_refresh.sh
```

This writes the wrapper log with resolved paths and exits before data refresh or
broker submission. It is the first command to run after installing the wrapper
on a new machine or changing recurring-run environment variables.

The older `scripts/run_paper_signal.sh` wrapper still exists for testing a known
static CSV, but it does not refresh data before generating a signal.

## Alpaca Paper Workflow

Run:

```bash
quant workflow alpaca-paper-refresh --symbol AAPL --start 2024-01-01 --from-env
```

This workflow performs one ordered sequence:

```text
fetch provider data
  -> write raw data
  -> write normalized market bars
  -> write validation report and metadata
  -> stop if validation fails
  -> generate the latest momentum signal
  -> calculate the long-only target position
  -> submit only the order required to reach that target
  -> write live order, fill, and account snapshot artifacts
  -> reconcile local artifacts against Alpaca paper broker state
  -> write workflow record
```

The workflow record is written under:

```text
data/workflows/alpaca-paper-refresh/
```

For Alpaca paper runs, that record includes the latest signal action, signal
reason, market price, whether broker submission was attempted, skip reason when
submission was not attempted, order/fill/snapshot artifact paths, and the
reconciliation report path. Target-based runs also record the broker position
before planning, strategy target quantity, and planned order side and quantity.
This lets a successful run distinguish "held with no order," "target position
already satisfied," and "submitted to the broker and reconciled."

The current momentum semantics are target-based: entry means long
`--quantity`, exit means flat, and hold means no inventory change. Existing
broker inventory determines the actual order side and quantity. Repeated
signals at the intended target submit no additional order.

See [alpaca_paper_workflow.md](alpaca_paper_workflow.md) for the design
context, safety policy, artifact contract, and non-goals.

Historical smoke and schedule evidence is documented in
[alpaca_paper_smoke_runbook.md](alpaca_paper_smoke_runbook.md) and
[alpaca_paper_schedule.md](alpaca_paper_schedule.md). Do not infer current
scheduler state or authorization from those records. Check runtime state
directly and obtain explicit approval before an order-capable run.

## Concurrent Run Safety

The refresh workflow uses a lock file by default:

```text
data/locks/paper-signal-refresh.lock
data/locks/dry-run-refresh.lock
data/locks/alpaca-paper-refresh.lock
```

If another run already holds the lock, the workflow fails before refreshing data
or touching downstream artifacts. It still writes a failed workflow record, so
the reason is auditable.

Locks become stale after `--lock-stale-after-seconds`, which defaults to `7200`
seconds. A later run can replace a stale lock. This is meant for crash recovery,
not for routinely running multiple workflows at once.

Inspect a lock with:

```bash
cat data/locks/paper-signal-refresh.lock
```

Only remove a lock manually after confirming no workflow process is still
running.

## Current Limits

Data Refresh Workflow v1 refreshes one symbol with one provider and then runs
one strategy. It does not yet reconcile multiple providers, refresh feature
artifacts, or support multi-symbol portfolios.
