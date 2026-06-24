# Supervised Provider Discovery-To-Loop Manual Synthetic Readiness Review

This document reviews the current discovery-to-loop operator evidence after
one synthetic manual dry-run from the runtime clone.

In plain language, this review asks:

```text
Are we ready to stop at manual synthetic dry-run readiness, or should we
broaden the operator workflow?
```

## Reviewed Evidence

The current evidence set includes:

- source-only promotion boundary;
- source-only promotion review;
- runtime-clone copy/import/help rehearsal;
- runtime-clone no-network actual-command rehearsal;
- manual operator runbook design;
- one synthetic manual discovery-to-loop dry-run from the runtime clone.

The latest manual run used:

```text
runtime commit: 56b45cc
request root: /tmp/quant-runtime-manual-discovery-loop-request
request file sha256: 8fb757c9519029c057e67151de289cd69f29f8c6d16ac1b925be4aff45885956
status: completed
```

The runtime clone stayed clean, runtime operational directory timestamps did
not change, the Alpaca paper launchd service stayed unloaded, and the
installed launchd plist stayed absent.

## Decision

The system is ready for **manual synthetic dry-run readiness**.

That means the current command can be trusted, within the reviewed boundary,
to run one synthetic reviewed request from the runtime clone while keeping
evidence under `/tmp` and avoiding operational paths.

This does not mean the system is ready for broader operator packaging.

## Why Not Broaden Yet

The evidence so far still does not cover:

- hand-authored production request preparation;
- request review by a second tool or human;
- long-lived runtime request directories;
- repeated human operations across market days;
- request archival outside `/tmp`;
- operator mistakes such as selecting the wrong request file;
- runtime cleanup policy;
- production data freshness;
- launchd, scheduler, semantic local paper, Alpaca, broker access, orders, or
  fills.

Those are different risks from proving that the command works with synthetic
reviewed inputs.

## Recommended Stop Point

Stop this promotion sequence here until there is a concrete need to run a
non-synthetic reviewed request.

The next work should return to research, strategy evaluation, or documentation
cleanup unless a specific operational request is proposed and reviewed.

## If A Future Non-Synthetic Request Is Needed

Design a separate stage before executing anything. That stage should define:

1. who or what creates the request;
2. where reviewed request files live;
3. how request hashes are reviewed;
4. how request age and freshness are enforced;
5. how output roots are isolated;
6. how artifacts are archived after the run;
7. how the operator proves `.env`, credentials, launchd, scheduler, paper,
   Alpaca, broker, order, and fill paths remain unused.

No future non-synthetic request should be run only because this synthetic
readiness review passed.

## Explicit Non-Authorization

This review does not authorize:

- preparing a production request;
- running a hand-authored request;
- recurring scheduling;
- launchd;
- runtime deployment;
- semantic local paper;
- Alpaca semantic targets;
- broker access;
- orders;
- fills;
- automatic drift repair.
