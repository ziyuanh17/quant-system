# Supervised Dry-Run Provider Contracts

## Purpose

The supervised dry-run service needs two inputs before every cycle:

1. evidence that the required system components are healthy;
2. one complete, fresh autonomous dry-run request.

This design defines those inputs precisely without choosing how they are
produced or delivered. It does not add request discovery, a scheduler, a
service manager, network access, paper trading, Alpaca, or broker access.

## Provider Policy

`SupervisedProviderPolicy` is the reviewed rule set shared by both providers.
It fixes:

```text
service identity
exact autonomous authorization revision
allowed health-source identity and version
allowed request-source identity and version
required health component names
maximum health age
maximum request age
```

A **provider** is simply a component that supplies an input. The provider
policy prevents an unreviewed or newly changed producer from silently feeding
the supervisor.

## Health Contract

`SupervisedHealthSnapshot` contains one named observation for every required
component. For example:

```text
strategy targets
account snapshot
reconciliation evidence
input data
```

Each component observation states:

```text
component identity
healthy, degraded, or failed
observation time
expiry time
reason and evidence references
```

The adapter converts the snapshot into the supervisor's existing durable
health check.

The result is:

- `healthy` only when every required component exists, is healthy, current,
  and from the allowed source;
- `degraded` for stale or explicitly degraded evidence;
- `failed` for missing, expired, future-dated, failed, wrong-cycle,
  wrong-service, or wrong-source evidence.

Both degraded and failed results stop the supervisor before request
generation.

## Fresh-Request Contract

`SupervisedRequestEnvelope` contains one complete
`AutonomousDryRunRequest` plus:

```text
service and cycle identity
request-source identity and version
generation and expiry times
source evidence
```

The adapter returns the request only when:

- service and cycle identities match;
- source identity and version match the provider policy;
- policy and request reference the exact authorization revision;
- the envelope is not future-dated, expired, or older than the allowed age;
- the request evaluation time equals the envelope generation time.

Any mismatch raises an error before the autonomous dry-run workflow starts.
The supervisor converts that error into a durable `error_stop` cycle event.

## Durable Input Artifacts

Immutable readers and writers are available for:

```text
policies/<service-id>.json
health-snapshots/<snapshot-id>.json
request-envelopes/<envelope-id>.json
```

Writers use exclusive creation and never overwrite an existing artifact.

## Review Boundary

This stage defines validation and persistence only. A future stage must
separately decide which local components build the health snapshot and request
envelope, where those artifacts are delivered, and how unavailable inputs are
reported. That future design must remain broker-free until separately
reviewed.
