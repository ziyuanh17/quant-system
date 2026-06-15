# Local Supervised Provider Assembly

## Purpose

The local provider assembly builds one supervised-service health snapshot and
one fresh-request envelope from exact reviewed semantic-target artifacts.

It is API-only and no-network. It does not run the supervised service, discover
new inputs, connect to a scheduler, deploy to the runtime clone, trade paper,
connect to Alpaca, or reach a broker.

## Content-Bound Manifest

`SupervisedProviderAssemblyManifest` is a reviewed bill of materials for one
cycle. It binds these files by exact path and SHA-256 content hash:

```text
supervised provider policy
bounded autonomous authorization
contributor set
strategy target decisions
strategy evaluations
```

The manifest also explicitly contains the dry-run-only operational inputs:

```text
risk policy
portfolio and risk target identities
dry-run account snapshot
execution policy
reference price
generation and expiry times
```

Any missing or changed reviewed file blocks assembly before output creation.

## Assembly Validation

The local assembly proceeds only when:

- the provider policy authorizes the exact local assembly source version;
- the provider policy and manifest reference the same service;
- the authorization is active at assembly time;
- contributor set, strategies, and account identity are authorized;
- strategy decisions and evaluations exactly match expected contributors;
- each evaluation references its matching available decision;
- targets aggregate actively and remain inside authorization limits;
- the dry-run account snapshot is current and not future-dated;
- the risk policy does not exceed authorization limits; and
- the provider policy requests only health components this assembly can prove.

## Outputs And Restart

One successful assembly writes:

```text
assemblies/<assembly-id>/manifest.json
assemblies/<assembly-id>/record.json
provider-inputs/health-snapshots/<assembly-id>-health.json
provider-inputs/request-envelopes/<assembly-id>-request.json
```

The output health snapshot reports three validated components:

```text
semantic-targets
dry-run-account
execution-inputs
```

The assembly record stores hashes for both outputs. Restart returns the same
record only after verifying the manifest and output files still match.

## Review Boundary

This stage proves deterministic local assembly from already reviewed files.
Its separate
[local no-network rehearsal](local_supervised_provider_assembly_rehearsal.md)
now covers successful assembly, restart, changed input, changed output, stale
target, stale account, and one complete provider-to-supervisor cycle.

Neither the assembly nor its rehearsal exposes CLI, deployment, scheduler,
paper, Alpaca, broker, or order-submission behavior.
