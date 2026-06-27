# Semantic-Target Alpaca Paper Runtime Rehearsal Design

Date: 2026-06-26

Status: In review

## Purpose

This document designs the next runtime-clone rehearsal before the first real
Alpaca paper order test. It is a software-infrastructure step. It verifies
that the runtime clone can see the reviewed source command and that all
paper-run preflight evidence can be captured without sourcing credentials,
contacting Alpaca, submitting orders, or changing scheduler state.

In plain language:

```text
Before we let the runtime clone submit one Alpaca paper order, prove that the
runtime environment has the command, the scheduler is absent, the runtime state
is understood, and the operator evidence checklist is ready.
```

## Scope

Allowed:

- fast-forward or verify the runtime clone at the reviewed source commit;
- inspect runtime git status;
- verify the semantic-target Alpaca paper command imports and shows help;
- verify scheduler absence;
- verify the launchd plist is absent;
- snapshot runtime operational directories;
- inspect environment-variable presence without printing secret values;
- write a no-network rehearsal evidence document in source docs.

Forbidden:

- source `.env`;
- print secrets;
- instantiate the real Alpaca paper client;
- contact Alpaca;
- submit paper orders;
- run `quant semantic-target alpaca-paper`;
- run legacy `quant workflow alpaca-paper-refresh`;
- load launchd;
- install or start a scheduler;
- mutate runtime evidence except for explicit, reviewed source fast-forwarding;
- clean unrelated runtime evidence;
- touch real-money trading.

## Reviewed Source

The runtime clone should be checked against the current reviewed branch commit
for `codex/semantic-paper-infra`.

Required source evidence:

```bash
cd /Users/mochifufu/Code/quant-system
git rev-parse --short HEAD
git status --short --branch
```

Required runtime evidence:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
git status --short --branch
git rev-parse --short HEAD
```

If the runtime clone is behind the reviewed source and otherwise safe to
fast-forward, the rehearsal may use an explicit `git fetch` plus
`git merge --ff-only` or equivalent approved fast-forward. If unrelated
runtime changes are present, stop and preserve them.

## Command Visibility Checks

After runtime source state is verified, run only import/help checks:

```bash
cd /Users/mochifufu/Code/quant-system-runtime
PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -c "import quant.cli"
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target --help
PYTHONDONTWRITEBYTECODE=1 .venv/bin/quant semantic-target alpaca-paper --help
```

Expected result:

- imports succeed;
- help text includes `--request-path`;
- help text includes `--from-env`;
- no `data/semantic-target/alpaca-paper` evidence is created;
- no order, fill, snapshot, reconciliation, scheduler, or workflow evidence is
  created by help checks.

## Scheduler And Launchd Checks

Record:

```bash
launchctl print "gui/$(id -u)/com.quant-system.alpaca-paper-refresh"
test ! -e "$HOME/Library/LaunchAgents/com.quant-system.alpaca-paper-refresh.plist"
```

Expected result:

- launchctl reports the service is not found;
- installed plist is absent.

If either check shows a loaded service or installed plist, stop before any
further rehearsal.

## Environment Presence Check

The no-network rehearsal may check whether expected variables are present, but
must not print values:

```text
QUANT_ALPACA_PAPER_API_KEY present or absent
QUANT_ALPACA_PAPER_SECRET_KEY present or absent
QUANT_ALPACA_PAPER_ACCOUNT_ID present or absent
QUANT_ALPACA_PAPER_URL_OVERRIDE present or absent
QUANT_BROKER present or absent
QUANT_MAX_ORDER_NOTIONAL present or absent
```

This is not permission to source `.env` or contact Alpaca. It only tells the
future operator whether credential plumbing is likely ready.

## Runtime Directory Snapshot

Record a before-and-after snapshot for:

```text
data/live/orders
data/live/fills
data/live/account_snapshots
data/live/reconciliation
data/semantic-target
data/workflows
data/scheduler
data/paper
data/web
logs
```

The rehearsal passes only if import/help checks do not create broker,
semantic-target, workflow, scheduler, order, fill, snapshot, or reconciliation
artifacts.

Existing `data/semantic-target` evidence may remain present. It must be
reported, not removed.

## Evidence Document

The actual rehearsal should produce a source-controlled evidence document with:

- source commit;
- runtime commit before and after;
- runtime git status before and after;
- command outputs for import/help checks;
- scheduler absence evidence;
- launchd plist absence evidence;
- environment presence summary without secrets;
- runtime directory snapshots before and after;
- explicit statement that no Alpaca call was made;
- explicit statement that no order-capable command was run.

## Pass Criteria

The rehearsal passes only if:

- source workspace starts clean;
- runtime clone has no unrelated tracked changes;
- reviewed source is visible in runtime;
- `quant semantic-target alpaca-paper --help` works from runtime;
- scheduler is not loaded;
- launchd plist is absent;
- no real Alpaca client is constructed;
- no Alpaca API call is made;
- no order, fill, snapshot, reconciliation, scheduler, or workflow artifact is
  created by the rehearsal;
- existing runtime evidence is preserved.

## Next Gate

After this rehearsal passes, the next stage may be a manual Alpaca paper run
with one reviewed request, provided fresh preflight evidence is captured
immediately before the paper API interaction.

That later paper run remains one request only and does not authorize launchd,
recurring scheduling, request discovery, non-paper Alpaca behavior, real-money
trading, automatic drift repair, or strategy research.
