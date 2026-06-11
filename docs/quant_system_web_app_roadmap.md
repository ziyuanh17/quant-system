# Quant System Web App Roadmap

This roadmap tracks the finite design and implementation path for the private
quant-system web console.

The web app begins as a read-only observer. It does not submit orders, approve
trades, change scheduler state, or modify trading configuration.

## Completion Definition

The first production-ready web app is complete only when:

- it is privately authenticated,
- it reads explicit sanitized API models rather than arbitrary runtime files,
- account environments and trading permissions are unambiguous,
- automatic decision traces explain signals, risk decisions, submissions,
  fills, skips, and failures,
- stale or missing evidence cannot appear healthy,
- operational, account, research, incident, and documentation views work on
  desktop and mobile,
- the application cannot mutate broker, scheduler, or safety state,
- deployment, rollback, monitoring, and security evidence are documented.

## Safety Invariants

- Keep the web app read-only through this roadmap.
- Never expose credentials, `.env`, raw account IDs, confirmation phrases, or
  raw broker payloads.
- Never describe a server as `live` without also displaying the exact broker
  environment and trading permission.
- Never infer an automatic decision from account position changes alone; use
  linked workflow, signal, risk, order, fill, and reconciliation evidence.
- Never let research promotion status enable paper or real-money execution.
- Keep the public GitHub Pages summary separate from the private console.
- Require a separate roadmap and threat model before adding any mutation or
  order-capable control.

## Milestones

| Order | Milestone | Status | Completion Evidence |
| --- | --- | --- | --- |
| W1 | Product, Information Architecture, and Safety Design | In Review | Web-app design, screen inventory, private/read-only boundary, automatic-decision visibility, and staged delivery plan documented. |
| W2 | Source Artifact and Data Classification | In Review | Every runtime, account, research, incident, and docs source is classified as public, private, sensitive, or prohibited, with candid truth/provenance rules. |
| W3 | Public and Private Read-Model Contracts | Planned | Typed, versioned, sanitized API models define overview, accounts, operations, decisions, research, incidents, and docs. |
| W4 | Freshness and Status Semantics | Planned | Shared rules define healthy, degraded, failed, running, disabled, unknown, and stale states with expected cadence. |
| W5 | Authentication and Private-Network Boundary | Planned | Private access, authentication, read-only authorization, secure headers, and access logging are designed and tested. |
| W6 | Read-Only API Foundation | Planned | API serves sanitized typed responses without arbitrary filesystem access or mutation endpoints. |
| W7 | Web Shell and Responsive Navigation | Planned | Desktop/mobile shell, navigation, loading, empty, stale, error, and unavailable states are implemented and visually verified. |
| W8 | Overview and Account-Lane Status | Planned | Overview distinguishes server health, broker environment, trading permission, reconciliation, freshness, and urgent issues. |
| W9 | Automatic Decision Trace v1 | Planned | Each automated evaluation explains trigger, inputs, signal, risk result, intended action, submission, fill, reconciliation, and stop reason. |
| W10 | Operations and Data-Freshness Console | Planned | Workflow history, scheduler ownership, locks, validation, dependencies, logs, versions, and reconciliation history are visible. |
| W11 | Account, Risk, and Performance Views | Planned | Local paper, dry-run, Alpaca paper, and real-money lanes expose authorized broker truth, risk utilization, and performance separately from health. |
| W12 | Knowledge Center and Docs Manifest | Planned | Repository Markdown is categorized, searchable, rendered safely, linked to live components, and marked canonical/historical/superseded. |
| W13 | Knowledge Publication Refresh | Planned | Knowledge and sanitized configuration/status snapshots support reviewed scheduled refresh and manual owner CLI/job refresh with atomic publication and stale/failure visibility. |
| W14 | System Explorer and Educational Flows | Planned | Interactive flow explains component purpose, inputs, outputs, safety boundaries, failure modes, docs, and recent evidence. |
| W15 | Incident Console | Planned | Active and resolved incidents link detection, containment, remediation, evidence, documents, and follow-up actions. |
| W16 | Research Console | Planned | Research families, candidates, trials, evaluations, reproducibility, and promotion recommendations are visible without execution controls. |
| W17 | Historical Observability and Alerts | Planned | Health, decisions, reconciliation, dependencies, resources, and portfolio/risk history support time-based investigation and alert routing. |
| W18 | Security, Redaction, and Failure-Mode Review | Planned | Redaction tests, authorization tests, stale-data tests, dependency failures, and prohibited-field checks pass. |
| W19 | Private Server Deployment Rehearsal | Planned | One controlled deployment proves authentication, read-only behavior, monitoring, backup, and rollback without affecting trading workflows. |
| W20 | First Natural Runtime Review | Planned | The deployed console correctly explains one natural workflow and automatic decision from trigger through reconciliation. |
| W21 | Web App v1 Closeout | Planned | Operational ownership, runbook, known limits, security boundary, and future roadmap are documented. |

## Automatic Decision Visibility

The console does not make automatic trading decisions. It observes and explains
the decisions made by scheduled quant workflows.

Canonical trace:

```text
scheduler or manual trigger
  -> data refresh and validation
  -> strategy evaluation
  -> signal decision
  -> portfolio/risk decision
  -> intended action
  -> broker submission or explicit skip/rejection
  -> order/fill terminal state
  -> account snapshot
  -> reconciliation
  -> health and alert result
```

For every automated decision, the console should answer:

```text
Why did evaluation run?
What exact data, strategy, and configuration were used?
What signal was produced?
What action was intended?
Which risk and safety gates passed or failed?
Was an order submitted, skipped, rejected, or blocked?
What did the broker report?
Did local records reconcile with broker truth?
What state changed, and what remains unresolved?
```

Decision outcomes:

```text
hold
would_submit
blocked_by_safety
blocked_by_risk
skipped_duplicate
submitted
partially_filled
filled
rejected
cancelled
timed_out
reconciliation_failed
```

The same trace shape applies to local paper, dry-run, Alpaca paper, and future
real-money environments. Fields that do not apply must be explicitly marked
`not_applicable`, not silently omitted.

## Recommended Build Order

```text
data classification
  -> sanitized read models
  -> freshness/status semantics
  -> authentication boundary
  -> read-only API
  -> responsive web shell
  -> overview and account lanes
  -> automatic decision trace
  -> operations and accounts
  -> knowledge center
  -> incidents and research
  -> historical observability
  -> security review
  -> controlled deployment
```

## Deferred Beyond V1

The following require a separate explicitly reviewed roadmap:

- order submission, cancellation, or replacement,
- human approval workflows,
- scheduler start/stop or configuration controls,
- risk-limit editing,
- strategy promotion into execution,
- real-money trading controls,
- public exposure of private console data.
