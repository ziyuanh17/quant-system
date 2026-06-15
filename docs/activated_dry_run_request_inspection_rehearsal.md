# Activated Dry-Run Request Inspection Rehearsal

## Purpose

This document records the June 14, 2026 local rehearsal of:

```bash
quant dry-run inspect-activated-target
```

Inspection reads and explains a reviewed dry-run request. It does not approve
the request, consume its one-use activation, run a dry-run, or create evidence
files.

## Synthetic Request

The rehearsal used fresh synthetic files under:

```text
/tmp/quant-activated-inspection-ccDJZh
```

The request described:

```text
symbol: AAPL
current position: 0 shares
approved target: +2 shares
reference price: $100
expected intended order: BUY 2 shares
expected notional: $200
```

The temporary request referenced passing base and activation-consumption
rehearsals and a time-limited dry-run authorization. It was not an operational
request and did not authorize a broker order.

## Observed Result

The actual command was run twice against the same request. Both runs exited
successfully and reported:

```text
valid now: yes
current position: 0 shares
approved target: 2 shares
intended order: BUY 2 shares
intended notional: $200
base rehearsal passed: yes
activation-consumption rehearsal passed: yes
```

## Read-Only Verification

Before the first inspection, the temporary request bundle contained 137 files.
After each inspection:

```text
file count: 137
all file SHA-256 hashes unchanged: yes
operator activation directory created: no
operator output directory created: no
```

Some prerequisite rehearsal inputs inside the request bundle contain
activation and fake local-paper evidence by design. Those files existed before
inspection and remained unchanged.

No broker client was constructed, no network call was made, no activation was
consumed, no dry-run workflow was run, and no runtime-clone state was changed.

## Verdict

The request inspection command passed its first actual local rehearsal. It
explained the reviewed request consistently across repeated runs and left all
input files unchanged.
