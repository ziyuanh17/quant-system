# Supervised Provider Request Discovery

This document describes the API-only reviewed request discovery contract for
the supervised semantic-target dry-run path.

Request discovery means: read a reviewed directory of
`SupervisedProviderOperatorRequest` JSON files, verify their hashes and
identity constraints, and produce one finite supervised-provider manifest. It
does not run the manifest, start a loop, discover work repeatedly, connect to a
scheduler, or reach paper, Alpaca, a broker, or runtime deployment.

## Contract

`SupervisedProviderDiscoveryPolicy` fixes:

- a safe discovery ID;
- a narrow `*.json` request glob;
- the reviewed request directory;
- the maximum number of requests allowed in one discovery pass;
- the finite loop ID and finite output root that the generated manifest will
  use;
- policy version, creation time, and evidence references.

`discover_supervised_provider_requests` then:

1. locks the discovery ID;
2. persists or verifies the immutable discovery policy;
3. scans only the configured reviewed directory;
4. fails closed if the directory is missing, empty, over the request limit, or
   contains requests with duplicate identities;
5. verifies every request file and every linked assembly manifest and
   assembly-rehearsal report by hash;
6. writes one immutable finite manifest when discovery completes;
7. writes one immutable discovery result, either `completed` or `blocked`.

Restarting the same discovery returns the same verified result. Changing a
completed request file or generated manifest causes verification to fail rather
than silently accepting new work.

## Safety Boundary

This stage intentionally stops before execution. A completed discovery result
only says, “these reviewed request files can form this exact finite manifest.”
The finite command or API must still be invoked separately to run the manifest.

There is no CLI for discovery in this stage. There is also no launchd,
runtime-clone, recurring scheduler, semantic local paper, Alpaca, broker, or
order-submission path.
