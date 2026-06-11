"""Historical observability API endpoints.."""

from datetime import datetime, timezone

from fastapi import APIRouter, Query

from quant.api.db import get_connection

router = APIRouter(tags=["history"])


@router.get("/history/status")
async def get_status_history(
    source: str = Query(default=""),
    state: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
) -> dict:
    """Status observations for charting.."""
    conn = get_connection()
    query = "SELECT * FROM status_observation WHERE 1=1"
    params = {}
    if source:
        query += " AND source = :source"
        params["source"] = source
    if state:
        query += " AND state = :state"
        params["state"] = state
    query += " ORDER BY observed_at DESC LIMIT :limit"
    params["limit"] = limit
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {
        "schema": {"schemaVersion": "v1", "generatedAt": datetime.now(timezone.utc).isoformat()},
        "observations": [dict(r) for r in rows],
       }


@router.get("/history/events")
async def get_event_history(
    component: str = Query(default=""),
    event_type: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
) -> dict:
    """Event timeline for charting.."""
    conn = get_connection()
    query = "SELECT * FROM event WHERE 1=1"
    params = {}
    if component:
        query += " AND component = :component"
        params["component"] = component
    if event_type:
        query += " AND event_type = :event_type"
        params["event_type"] = event_type
    query += " ORDER BY timestamp DESC LIMIT :limit"
    params["limit"] = limit
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {
        "schema": {"schemaVersion": "v1", "generatedAt": datetime.now(timezone.utc).isoformat()},
        "events": [dict(r) for r in rows],
       }


@router.get("/history/reconciliation")
async def get_reconciliation_history(
    environment: str = Query(default=""),
    limit: int = Query(default=100, le=1000),
) -> dict:
    """Reconciliation history for charting.."""
    conn = get_connection()
    query = "SELECT * FROM reconciliation WHERE 1=1"
    params = {}
    if environment:
        query += " AND environment = :environment"
        params["environment"] = environment
    query += " ORDER BY observed_at DESC LIMIT :limit"
    params["limit"] = limit
    rows = conn.execute(query, params).fetchall()
    conn.close()
    return {
        "schema": {"schemaVersion": "v1", "generatedAt": datetime.now(timezone.utc).isoformat()},
        "reconciliations": [dict(r) for r in rows],
       }
