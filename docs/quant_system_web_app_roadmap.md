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
| W1 | Product, Information Architecture, and Safety Design | Done | Web-app design, screen inventory, private/read-only boundary, automatic-decision visibility, and staged delivery plan documented (`docs/quant_system_web_app_design.md`). |
| W2 | Source Artifact and Data Classification | Done | Source classification documented (`docs/quant_system_web_app_source_classification.md`). |
| W3 | Public and Private Read-Model Contracts | Done | 561 lines of typed Pydantic models in `src/quant/api/models.py` define overview, accounts, operations, decisions, research, incidents, docs, system, and root endpoints. |
| W4 | Freshness and Status Semantics | Done | `src/quant/api/freshness.py` (235 lines) implements shared rules for healthy, degraded, failed, running, disabled, unknown, and stale states. |
| W5 | Authentication and Private-Network Boundary | Done | `src/quant/api/auth.py` (160 lines) implements API key auth, access logging, and secure headers middleware. |
| W6 | Read-Only API Foundation | Done | `src/quant/web/app.py` mounts read-only API at `/api/v1/*` and HTML pages at `/*`. No mutation endpoints. |
| W7 | Web Shell and Responsive Navigation | Done | 10 Jinja2 templates (`src/quant/web/templates/`) plus static assets provide desktop/mobile shell with navigation rail, top bar, and evidence drawer. |
| W8 | Overview and Account-Lane Status | Done | `/overview` page with system status, 4 account lanes, latest decisions, workflows, issues, freshness, research queue, and source version. |
| W9 | Automatic Decision Trace v1 | Done | `/decisions` page with full decision trace (trigger → signal → risk → submission → fill → reconciliation). |
| W10 | Operations and Data-Freshness Console | Done | `/operations` page with workflow history, scheduler ownership, locks, validation, dependencies, logs, versions, reconciliation history. |
| W11 | Account, Risk, and Performance Views | Done | `/accounts` page with identity, permission, broker truth, risk/exposure, and performance sections per environment. |
| W12 | Knowledge Center and Docs Manifest | Done | `/knowledge` page renders and categorizes `docs/` Markdown into collections with full-text search. |
| W13 | Knowledge Publication Refresh | Done | `src/quant/web/docs_index.py` builds searchable docs index; `quant ops publish-knowledge` writes `site/knowledge_index.json`; 26 tests pass. |
| W14 | System Explorer and Educational Flows | Done | `/system` page with interactive component flow diagram, purpose/inputs/outputs/safety boundaries/failure modes. |
| W15 | Incident Console | Done | `/incidents` page with active/resolved incidents, timeline, evidence links, and follow-up actions. |
| W16 | Research Console | Done | `/research` page with research families, candidates, trials, evaluations, reproducibility, and promotion recommendations. |
| W17 | Historical Observability and Alerts | Done | SQLite-backed `/history` page with status observation, event, and reconciliation tables (`src/quant/api/db.py`). |
| W18 | Security, Redaction, and Failure-Mode Review | Done | `tests/test_web_security.py` (16 tests) covers redaction, no-mutation endpoints, stale data, and auth gates. `require_api_key` wired to all routes via `Depends()`. All 268 tests pass. |
| W19 | Private Server Deployment Rehearsal | Done | `src/quant/web/serve.py` wraps uvicorn; `quant web serve` CLI command; launchd plist template in `configs/launchd/`; deployment docs in `docs/console_deployment.md`; `.env.example` updated. |
| W20 | First Natural Runtime Review | Done | All API routes wired to real data: `overview()` calls `build_health_report()`, `accounts()` reads paper state, `incidents()` scans `docs/`, `system()` counts artifact files, `operations()` scans workflow dirs. |
| W21 | Web App v1 Closeout | Done | `docs/console_runbook.md`, `docs/console_known_limits.md`, `docs/console_security_boundary.md`, `docs/console_future_roadmap.md` created; `README.md` and `docs/runbook.md` updated; roadmap marked complete. |
| W22 | Restart-Safe Private Tailscale Deployment | Done | Reviewed source was promoted to the runtime clone; a dedicated API key was configured; the console launchd service is running from the runtime clone; tailnet-only Tailscale Serve HTTPS and authenticated API access passed. |

## Current Deployment State

As of June 12, 2026:

- the source-side restart-safe deployment bundle is implemented and passes the
  full repository quality gate,
- the Mac Studio is connected to Tailscale as
  `mochifufus-mac-studio.tail2d964e.ts.net`,
- private Tailscale Serve is active at
  `https://mochifufus-mac-studio.tail2d964e.ts.net/` and proxies only to
  `http://127.0.0.1:8000`,
- a development-clone wrapper rehearsal failed closed because no
  `QUANT_CONSOLE_API_KEY` is configured,
- reviewed source commit `65f43ca` is promoted to the runtime clone,
- the runtime clone has a dedicated untracked console API key,
- launchd service `com.quant-system.console` is running from the runtime clone,
  with one run and no exit,
- localhost page access, unauthenticated rejection, authenticated API access,
  and tailnet HTTPS access all passed.

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
