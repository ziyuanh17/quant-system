"""API root and overview endpoints.

Provides schema discovery and a sanitized overview of system state.

"""

from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter

from quant.api.freshness import EXPECTED_FRESHNESS
from quant.api.models import (
    AccountLane,
    ApiRootResponse,
    Environment,
    OverviewResponse,
    OverviewResearchQueue,
    OverviewSource,
    OverviewSystem,
    Status,
    StatusValue,
)

router = APIRouter()

# Default data directories (overridden at runtime)
_DATA_DIR = Path("data")


@router.get("/", response_model=ApiRootResponse)
async def root() -> ApiRootResponse:
    """Schema discovery: list all available API endpoints."""
    return ApiRootResponse()


def _not_configured(source: str = "system") -> Status:
    """Return a not_configured status for an unpopulated data source."""
    return Status(
        state=StatusValue.NOT_CONFIGURED,
        severity="ok",
        observed_at=datetime.now(timezone.utc),
        source_updated_at=None,
        expected_freshness_seconds=EXPECTED_FRESHNESS.get(source, 3600),
        is_stale=False,
        source_type=source,
        message="not configured",
    )


@router.get("/overview", response_model=OverviewResponse)
async def overview() -> OverviewResponse:
    """Return a sanitized overview of system state.

    Returns not_configured for any source that does not yet have
    artifacts. Never exposes sensitive data.

    """
    now = datetime.now(timezone.utc)

    def _nc(source: str) -> Status:
        return _not_configured(source)

    return OverviewResponse(
        system=OverviewSystem(
            server_status=_nc("health_check"),
            server_heartbeat=_nc("health_check"),
            trading_permission="disabled",
            market_state="unknown",
            urgent_issue=None,
            next_action=None,
        ),
        account_lanes=(
            AccountLane(
                environment=Environment.LOCAL_PAPER,
                connection=_nc("paper_state"),
                permission="simulated",
                reconciliation=_nc("reconciliation"),
                freshness=_nc("paper_state"),
            ),
            AccountLane(
                environment=Environment.DRY_RUN,
                connection=_nc("paper_state"),
                permission="record only",
                reconciliation=_nc("reconciliation"),
                freshness=_nc("paper_state"),
            ),
            AccountLane(
                environment=Environment.ALPACA_PAPER,
                connection=_nc("broker_snapshot"),
                permission="paper orders",
                reconciliation=_nc("reconciliation"),
                freshness=_nc("broker_snapshot"),
            ),
            AccountLane(
                environment=Environment.REAL_MONEY,
                connection=_not_configured(),
                permission="not_configured",
                reconciliation=_not_configured(),
                freshness=_not_configured(),
            ),
        ),
        latest_workflows=[],
        latest_reconciliation=None,
        issues=[],
        data_freshness={},
        research_queue=OverviewResearchQueue(),
        source=OverviewSource(),
    )
