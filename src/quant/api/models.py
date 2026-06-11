"""API read-model contracts for the quant-system web console.

These Pydantic models define the shape of every sanitized API response.
They are the public contract between the backend and the frontend —
the frontend must never read raw runtime files directly.

Each response model includes:
- Freshness metadata (observed time, source time, expected cadence)
- Explicit unavailable/not_configured states for missing evidence
- No sensitive fields (credentials, raw account IDs, broker payloads)

"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import ConfigDict, Field
from pydantic.alias_generators import to_camel

from quant.models.base import FrozenModel


class ApiModel(FrozenModel):
    """Base for browser-facing models serialized with camelCase aliases."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )


# ---------------------------------------------------------------------------
# Freshness and status semantics (shared across all endpoints)
# ---------------------------------------------------------------------------


class StatusValue(StrEnum):
    """Canonical status values for every observable component."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    FAILED = "failed"
    RUNNING = "running"
    DISABLED = "disabled"
    NOT_CONFIGURED = "not_configured"
    UNKNOWN = "unknown"
    STALE = "stale"


class Severity(StrEnum):
    """Severity levels for status messages."""

    OK = "ok"
    WARNING = "warning"
    ERROR = "error"


class Status(ApiModel):
    """One status observation with freshness metadata.

    Every displayed status must carry these fields so the user can
    distinguish fresh healthy from stale-appearing-healthy.
    """

    state: StatusValue
    severity: Severity = Severity.OK
    observed_at: datetime
    source_updated_at: datetime | None = None
    expected_freshness_seconds: int | None = None
    is_stale: bool = False
    source_type: str = "unknown"
    evidence_ref: str | None = None
    message: str = ""


class SchemaVersion(ApiModel):
    """Schema version and generation metadata for every API response."""

    schema_version: str = "v1"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Environment and account models
# ---------------------------------------------------------------------------


class Environment(StrEnum):
    LOCAL_PAPER = "local-paper"
    DRY_RUN = "dry-run"
    ALPACA_PAPER = "alpaca-paper"
    REAL_MONEY = "real-money"


class AccountLane(ApiModel):
    """One trading environment lane on the Overview page."""

    environment: Environment
    connection: Status
    permission: str
    reconciliation: Status
    open_orders: int = 0
    positions: int = 0
    freshness: Status


class AccountDetailPermission(ApiModel):
    """Identity and permission for one account."""

    environment: Environment
    broker: str
    account_alias: str  # redacted; never raw account ID
    connection: Status
    trading_permission: str
    safety_gate_status: Status
    max_order_notional: float | None = None
    risk_limits: dict[str, float | None] = Field(default_factory=dict)
    last_snapshot_at: datetime | None = None


class AccountDetailRisk(ApiModel):
    """Risk and exposure metrics for one account."""

    gross_exposure: float | None = None
    net_exposure: float | None = None
    long_exposure: float | None = None
    short_exposure: float | None = None
    concentration: dict[str, float] = Field(default_factory=dict)
    buying_power_buffer: float | None = None
    limits_utilized: dict[str, float | None] = Field(default_factory=dict)
    stale_price_warning: bool = False
    unavailable_borrow_warning: bool = False


class AccountDetailPerformance(ApiModel):
    """Performance metrics for one account."""

    equity: float | None = None
    cash: float | None = None
    daily_return: float | None = None
    unrealized_pnl: float | None = None
    realized_pnl: float | None = None
    drawdown: float | None = None
    turnover: float | None = None
    commissions: float | None = None
    benchmark_comparison: float | None = None


class AccountDetail(ApiModel):
    """Full account view for one environment (Accounts page)."""

    permission: AccountDetailPermission
    risk: AccountDetailRisk
    performance: AccountDetailPerformance
    positions: list[dict[str, Any]] = Field(default_factory=list)
    open_orders: list[dict[str, Any]] = Field(default_factory=list)
    recent_fills: list[dict[str, Any]] = Field(default_factory=list)
    reconciliation: Status | None = None
    latest_decision: DecisionTrace | None = None


# ---------------------------------------------------------------------------
# Decision trace models
# ---------------------------------------------------------------------------


class DecisionOutcome(StrEnum):
    """Canonical automatic decision outcomes."""

    HOLD = "hold"
    WOULD_SUBMIT = "would_submit"
    BLOCKED_BY_SAFETY = "blocked_by_safety"
    BLOCKED_BY_RISK = "blocked_by_risk"
    SKIPPED_DUPLICATE = "skipped_duplicate"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    REJECTED = "rejected"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"
    RECONCILIATION_FAILED = "reconciliation_failed"


class RiskGateResult(ApiModel):
    """One risk or safety gate with pass/fail evidence."""

    name: str
    passed: bool
    evidence: str = ""


class DecisionTrace(ApiModel):
    """Complete trace of one automatic evaluation decision.

    Every step from trigger through reconciliation is recorded so the
    user can understand why a decision was made.
    """

    trigger_source: str  # "scheduler" or "manual"
    is_scheduled: bool
    strategy: str
    strategy_version: str
    source_commit: str
    input_data: str  # dataset identifier
    signal: str
    signal_reason: str
    intended_side: str | None = None
    intended_quantity: int | None = None
    intended_price_reference: float | None = None
    intended_notional: float | None = None
    risk_gates: tuple[RiskGateResult, ...] = ()
    submission_attempted: bool | None = None
    submission_reason: str | None = None
    broker_result: str | None = None
    order_state: str | None = None
    fill_state: str | None = None
    before_snapshot: dict[str, Any] | None = None
    after_snapshot: dict[str, Any] | None = None
    reconciliation: Status | None = None
    outcome: DecisionOutcome
    stop_reason: str | None = None
    observed_at: datetime


# ---------------------------------------------------------------------------
# Overview response
# ---------------------------------------------------------------------------


class OverviewSystem(ApiModel):
    """System-level status for the Overview page."""

    server_status: Status
    server_heartbeat: Status
    host: str | None = None
    trading_permission: str
    market_state: str  # "open", "closed", "unknown"
    urgent_issue: str | None = None
    next_action: str | None = None


class OverviewResearchQueue(ApiModel):
    """Research promotion queue on the Overview page."""

    candidates_pending: int = 0
    candidates: list[dict[str, Any]] = Field(default_factory=list)


class OverviewSource(ApiModel):
    """Source/configuration version on the Overview page."""

    source_commit: str | None = None
    config_version: str | None = None


class OverviewResponse(ApiModel):
    """Response for GET /api/v1/overview."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    system: OverviewSystem
    account_lanes: tuple[AccountLane, ...]
    latest_decisions: dict[Environment, DecisionTrace | None] = Field(
        default_factory=dict,
    )
    latest_workflows: list[dict[str, Any]] = Field(default_factory=list)
    latest_reconciliation: Status | None = None
    issues: list[dict[str, Any]] = Field(default_factory=list)
    data_freshness: dict[str, Status] = Field(default_factory=dict)
    research_queue: OverviewResearchQueue = Field(
        default_factory=lambda: OverviewResearchQueue(),
    )
    source: OverviewSource = Field(
        default_factory=lambda: OverviewSource(),
    )


# ---------------------------------------------------------------------------
# Operations responses
# ---------------------------------------------------------------------------


class PaginatedResponse(ApiModel):
    """Mixin for paginated list responses."""

    total: int = 0
    page: int = 1
    page_size: int = 50
    items: list[dict[str, Any]] = Field(default_factory=list)


class OperationsRunsResponse(PaginatedResponse):
    """Response for GET /api/v1/operations/runs."""

    run_type: str = "all"  # "workflow", "scheduled", or "all"


class OperationsEvent(ApiModel):
    """One operational event for the events timeline."""

    timestamp: datetime
    event_type: str
    component: str
    status: StatusValue
    message: str
    workflow_id: str | None = None
    evidence_ref: str | None = None


class OperationsEventsResponse(PaginatedResponse):
    """Response for GET /api/v1/operations/events."""


# ---------------------------------------------------------------------------
# Accounts responses
# ---------------------------------------------------------------------------


class AccountSummary(ApiModel):
    """Compact account summary for the accounts list."""

    environment: Environment
    broker: str
    account_alias: str
    connection: Status
    trading_permission: str
    equity: float | None = None
    cash: float | None = None
    position_count: int = 0
    open_order_count: int = 0
    reconciliation: Status | None = None
    freshness: Status


class AccountsListResponse(ApiModel):
    """Response for GET /api/v1/accounts."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    accounts: tuple[AccountSummary, ...]


# ---------------------------------------------------------------------------
# Research responses
# ---------------------------------------------------------------------------


class ResearchFamilySummary(ApiModel):
    """One research family on the families list."""

    family_id: str
    name: str
    candidate_count: int = 0
    latest_evaluation_at: datetime | None = None
    recommendation: str | None = None


class ResearchFamiliesResponse(ApiModel):
    """Response for GET /api/v1/research/families."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    families: tuple[ResearchFamilySummary, ...]


class ResearchCandidateDetail(ApiModel):
    """Detail for one research candidate."""

    candidate_id: str
    family_id: str
    hypothesis: str
    strategy_name: str
    strategy_version: str
    parameters: list[dict[str, Any]] = Field(default_factory=list)
    symbols: tuple[str, ...] = ()
    split_policy: dict[str, Any] | None = None
    evaluation_results: dict[str, Any] | None = None
    comparison: dict[str, Any] | None = None
    recommendation: dict[str, Any] | None = None
    trial_count: int = 0
    trials: list[dict[str, Any]] = Field(default_factory=list)
    data_lineage: list[dict[str, Any]] = Field(default_factory=list)
    reproducibility_status: Status | None = None
    promotion_recommendation: str | None = None


class ResearchCandidateResponse(ApiModel):
    """Response for GET /api/v1/research/candidates/{candidate-id}."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    candidate: ResearchCandidateDetail


# ---------------------------------------------------------------------------
# Incident responses
# ---------------------------------------------------------------------------


class IncidentSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentTimelineEntry(ApiModel):
    """One entry in an incident timeline."""

    timestamp: datetime
    phase: str  # "detected", "contained", "remediated", "resolved"
    message: str
    evidence_ref: str | None = None


class IncidentSummary(ApiModel):
    """Compact incident summary for the incidents list."""

    incident_id: str
    title: str
    severity: IncidentSeverity
    status: str  # "active" or "resolved"
    detected_at: datetime | None = None
    resolved_at: datetime | None = None
    impacted_environments: tuple[Environment, ...] = ()
    unresolved_actions: int = 0


class IncidentDetail(ApiModel):
    """Full incident detail."""

    incident_id: str
    title: str
    severity: IncidentSeverity
    status: str
    description: str
    timeline: tuple[IncidentTimelineEntry, ...] = ()
    linked_evidence: list[dict[str, Any]] = Field(default_factory=list)
    linked_document: str | None = None
    unresolved_actions: list[dict[str, Any]] = Field(default_factory=list)
    impacted_environments: tuple[Environment, ...] = ()


class IncidentsListResponse(ApiModel):
    """Response for GET /api/v1/incidents."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    active: tuple[IncidentSummary, ...]
    resolved: tuple[IncidentSummary, ...]


# ---------------------------------------------------------------------------
# Documentation responses
# ---------------------------------------------------------------------------


class DocCollection(StrEnum):
    START_HERE = "start_here"
    OPERATE = "operate"
    SAFETY_AND_BROKER = "safety_and_broker"
    RESEARCH_AND_DATA = "research_and_data"
    MIGRATION_AND_SCHEDULING = "migration_and_scheduling"
    INCIDENTS_AND_REHEARSALS = "incidents_and_rehearsals"
    PROJECT_MANAGEMENT = "project_management"


class DocType(StrEnum):
    CANONICAL_GUIDANCE = "canonical_guidance"
    RUNBOOK = "runbook"
    DESIGN = "design"
    INCIDENT = "incident"
    HISTORICAL_EVIDENCE = "historical_evidence"


class DocSummary(ApiModel):
    """Compact document summary for the docs list."""

    slug: str
    title: str
    collection: DocCollection
    doc_type: DocType
    summary: str = ""
    last_modified: datetime | None = None
    source_commit: str | None = None
    status: str  # "current", "superseded", "historical"
    superseded_by: str | None = None


class DocDetail(ApiModel):
    """Full document detail with rendered content."""

    slug: str
    title: str
    collection: DocCollection
    doc_type: DocType
    summary: str = ""
    toc: list[dict[str, str]] = Field(default_factory=list)
    rendered_content: str = ""
    last_modified: datetime | None = None
    source_commit: str | None = None
    status: str
    superseded_by: str | None = None
    related_components: list[str] = Field(default_factory=list)
    related_documents: list[str] = Field(default_factory=list)
    glossary_terms: list[dict[str, str]] = Field(default_factory=list)


class DocsListResponse(ApiModel):
    """Response for GET /api/v1/docs."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    docs: tuple[DocSummary, ...]
    collections: tuple[DocCollection, ...]


class DocsDetailResponse(ApiModel):
    """Response for GET /api/v1/docs/{slug}."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    document: DocDetail


# ---------------------------------------------------------------------------
# System component responses
# ---------------------------------------------------------------------------


class SystemComponent(ApiModel):
    """One component in the system flow."""

    name: str
    purpose: str
    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    implementation_status: str  # "implemented", "partial", "design", "none"
    failure_modes: list[str] = Field(default_factory=list)
    safety_boundary: str = ""
    recent_runs: int = 0
    recent_issues: int = 0


class SystemComponentsResponse(ApiModel):
    """Response for GET /api/v1/system/components."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    components: tuple[SystemComponent, ...]


# ---------------------------------------------------------------------------
# Root response (schema discovery)
# ---------------------------------------------------------------------------


class ApiRootResponse(ApiModel):
    """Response for GET /api/v1 — schema discovery."""

    response_schema: SchemaVersion = Field(default_factory=SchemaVersion)
    endpoints: dict[str, str] = Field(
        default_factory=lambda: {
            "overview": "/api/v1/overview",
            "operations_runs": "/api/v1/operations/runs",
            "operations_events": "/api/v1/operations/events",
            "accounts": "/api/v1/accounts",
            "accounts_detail": "/api/v1/accounts/{account-alias}",
            "research_families": "/api/v1/research/families",
            "research_candidate": "/api/v1/research/candidates/{id}",
            "incidents": "/api/v1/incidents",
            "docs": "/api/v1/docs",
            "docs_detail": "/api/v1/docs/{slug}",
            "system_components": "/api/v1/system/components",
        },
    )
