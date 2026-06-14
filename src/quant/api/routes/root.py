"""API root and overview endpoints."""

from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key
from quant.api.freshness import EXPECTED_FRESHNESS
from quant.api.models import (
    AccountLane,
    ApiRootResponse,
    DecisionOutcome,
    DecisionTrace,
    Environment,
    OverviewResearchQueue,
    OverviewResponse,
    OverviewSource,
    OverviewSystem,
    Severity,
    Status,
    StatusValue,
)
from quant.operations import build_health_report

router = APIRouter()

# Default data directories (overridden at runtime)
_DATA_DIR = Path("data")


def _decision_outcome(action: str | None) -> DecisionOutcome:
    """Map a signal action to a conservative observable outcome."""
    if action == "hold":
        return DecisionOutcome.HOLD
    return DecisionOutcome.WOULD_SUBMIT


@router.get("/", response_model=ApiRootResponse, dependencies=[])
async def root() -> ApiRootResponse:
    """Schema discovery: list all available API endpoints."""
    return ApiRootResponse()


def _status_from_health(
    state: str,
    source: str,
    is_stale: bool = False,
    message: str = "",
) -> Status:
    """Convert a health report string field to a Status model."""
    state_map = {
        "healthy": StatusValue.HEALTHY,
        "degraded": StatusValue.DEGRADED,
        "failed": StatusValue.FAILED,
        "running": StatusValue.RUNNING,
        "disabled": StatusValue.DISABLED,
        "not_configured": StatusValue.NOT_CONFIGURED,
        "unknown": StatusValue.UNKNOWN,
        "stale": StatusValue.STALE,
        "skipped": StatusValue.UNKNOWN,
    }
    return Status(
        state=state_map.get(state, StatusValue.UNKNOWN),
        severity=Severity.OK
        if state in ("healthy", "not_configured", "skipped")
        else Severity.ERROR,
        observed_at=datetime.now(UTC),
        source_updated_at=None,
        expected_freshness_seconds=EXPECTED_FRESHNESS.get(source, 3600),
        is_stale=is_stale,
        source_type=source,
        message=message,
    )


@router.get(
    "/overview",
    response_model=OverviewResponse,
    dependencies=[Depends(require_api_key)],
)
async def overview() -> OverviewResponse:
    """Return a sanitized overview of system state.."""
    try:
        report = build_health_report(
            run_records_dir=_DATA_DIR / "scheduler" / "latest",
            signal_records_dir=_DATA_DIR / "paper" / "signals",
            state_path=_DATA_DIR / "paper" / "state" / "default.json",
            logs_dir=_DATA_DIR / "logs",
            lock_path=_DATA_DIR / "locks" / "paper-signal-refresh.lock",
            lock_stale_after_seconds=7200,
            reconcile_state=True,
            initial_cash=100_000,
            cash_tolerance=0.01,
            check_paper_service=True,
            check_comparison=True,
            comparison_report_path=_DATA_DIR
            / "dry_run"
            / "comparison"
            / "latest.json",
            check_alpaca_paper=True,
            alpaca_paper_workflow_records_dir=_DATA_DIR
            / "workflows"
            / "alpaca-paper-refresh",
            alpaca_paper_reconciliation_report_path=_DATA_DIR
            / "live"
            / "reconciliation"
            / "latest.json",
        )
    except Exception:
        # If build_health_report fails (e.g. missing data dirs),
        # return not_configured for everything
        return OverviewResponse(
            system=OverviewSystem(
                server_status=_status_from_health(
                    "failed", "health_check", message="health check unavailable"
                ),
                server_heartbeat=_status_from_health(
                    "failed", "health_check", message="heartbeat unavailable"
                ),
                trading_permission="disabled",
                market_state="unknown",
                urgent_issue="Health check failed",
                next_action=None,
            ),
            account_lanes=(
                AccountLane(
                    environment=Environment.LOCAL_PAPER,
                    connection=_status_from_health(
                        "unknown", "paper_state", message="unavailable"
                    ),
                    permission="simulated",
                    reconciliation=_status_from_health(
                        "unknown", "reconciliation", message="unavailable"
                    ),
                    freshness=_status_from_health(
                        "unknown", "paper_state", message="unavailable"
                    ),
                ),
                AccountLane(
                    environment=Environment.DRY_RUN,
                    connection=_status_from_health(
                        "unknown", "paper_state", message="unavailable"
                    ),
                    permission="record only",
                    reconciliation=_status_from_health(
                        "unknown", "reconciliation", message="unavailable"
                    ),
                    freshness=_status_from_health(
                        "unknown", "paper_state", message="unavailable"
                    ),
                ),
                AccountLane(
                    environment=Environment.ALPACA_PAPER,
                    connection=_status_from_health(
                        "unknown", "broker_snapshot", message="unavailable"
                    ),
                    permission="paper orders",
                    reconciliation=_status_from_health(
                        "unknown", "reconciliation", message="unavailable"
                    ),
                    freshness=_status_from_health(
                        "unknown", "broker_snapshot", message="unavailable"
                    ),
                ),
                AccountLane(
                    environment=Environment.REAL_MONEY,
                    connection=_status_from_health(
                        "not_configured", "real_money", message="not configured"
                    ),
                    permission="not_configured",
                    reconciliation=_status_from_health(
                        "not_configured", "real_money", message="not configured"
                    ),
                    freshness=_status_from_health(
                        "not_configured", "real_money", message="not configured"
                    ),
                ),
            ),
            latest_workflows=[],
            latest_reconciliation=None,
            issues=[],
            data_freshness={},
            research_queue=OverviewResearchQueue(),
            source=OverviewSource(),
        )

    # Convert health report to overview response
    system = OverviewSystem(
        server_status=_status_from_health(
            "healthy" if report.status.value == "healthy" else "failed",
            "health_check",
            message=str(report.status.value),
        ),
        server_heartbeat=_status_from_health(
            "healthy",
            "health_check",
        ),
        trading_permission="paper only",
        market_state="unknown",
        urgent_issue=report.issues[0].message if report.issues else None,
        next_action=None,
    )

    # Build account lanes from health report
    paper_connection = _status_from_health(
        "healthy" if report.latest_run_status == "succeeded" else "degraded",
        "paper_state",
    )
    paper_recon = _status_from_health(
        report.reconciliation_status,
        "reconciliation",
    )
    paper_freshness = _status_from_health(
        "healthy" if report.latest_signal_path else "unknown",
        "paper_state",
    )

    alpaca_connection = _status_from_health(
        report.alpaca_paper_workflow_status
        if report.alpaca_paper_workflow_status != "skipped"
        else "unknown",
        "broker_snapshot",
    )
    alpaca_recon = _status_from_health(
        report.alpaca_paper_reconciliation_status,
        "reconciliation",
    )

    account_lanes = (
        AccountLane(
            environment=Environment.LOCAL_PAPER,
            connection=paper_connection,
            permission="simulated",
            reconciliation=paper_recon,
            open_orders=0,
            positions=report.state_position_count or 0,
            freshness=paper_freshness,
        ),
        AccountLane(
            environment=Environment.DRY_RUN,
            connection=_status_from_health(
                report.comparison_status, "paper_state"
            ),
            permission="record only",
            reconciliation=_status_from_health(
                report.comparison_status, "reconciliation"
            ),
            freshness=_status_from_health(
                report.comparison_status, "paper_state"
            ),
        ),
        AccountLane(
            environment=Environment.ALPACA_PAPER,
            connection=alpaca_connection,
            permission="paper orders"
            if report.alpaca_paper_workflow_status != "skipped"
            else "disabled",
            reconciliation=alpaca_recon,
            open_orders=0,
            positions=0,
            freshness=alpaca_connection,
        ),
        AccountLane(
            environment=Environment.REAL_MONEY,
            connection=_status_from_health(
                "not_configured", "real_money", message="not configured"
            ),
            permission="not_configured",
            reconciliation=_status_from_health(
                "not_configured", "real_money", message="not configured"
            ),
            freshness=_status_from_health(
                "not_configured", "real_money", message="not configured"
            ),
        ),
    )

    # Build latest decisions from health report
    latest_decisions: dict[Environment, DecisionTrace | None] = {}

    if report.latest_signal_path:
        latest_decisions[Environment.LOCAL_PAPER] = DecisionTrace(
            trigger_source="scheduler",
            is_scheduled=True,
            strategy="momentum",
            strategy_version="v1",
            source_commit="unknown",
            input_data=Path(report.latest_signal_path).name,
            signal=report.latest_signal_action or "hold",
            signal_reason="",
            outcome=_decision_outcome(report.latest_signal_action),
            observed_at=report.checked_at,
        )

    if report.alpaca_paper_workflow_path:
        latest_decisions[Environment.ALPACA_PAPER] = DecisionTrace(
            trigger_source="scheduler",
            is_scheduled=True,
            strategy="momentum",
            strategy_version="v1",
            source_commit="unknown",
            input_data=Path(report.alpaca_paper_workflow_path).name,
            signal=report.alpaca_paper_latest_signal_action or "hold",
            signal_reason=report.alpaca_paper_latest_signal_reason or "",
            outcome=_decision_outcome(report.alpaca_paper_latest_signal_action),
            observed_at=report.checked_at,
        )

    return OverviewResponse(
        system=system,
        account_lanes=account_lanes,
        latest_decisions=latest_decisions,
        latest_workflows=[
            {
                "workflow_id": "latest",
                "status": report.status.value,
                "completed_at": report.checked_at.isoformat(),
                "message": report.issues[0].message if report.issues else "ok",
            }
        ],
        latest_reconciliation=_status_from_health(
            report.reconciliation_status,
            "reconciliation",
        ),
        issues=[
            {
                "code": issue.code,
                "severity": issue.severity.value,
                "message": issue.message,
            }
            for issue in report.issues
        ],
        data_freshness={
            "paper_state": _status_from_health(
                "healthy" if report.latest_signal_path else "unknown",
                "paper_state",
            ),
            "reconciliation": _status_from_health(
                report.reconciliation_status,
                "reconciliation",
            ),
        },
        research_queue=OverviewResearchQueue(),
        source=OverviewSource(
            source_commit="unknown",
            config_version="unknown",
        ),
    )
