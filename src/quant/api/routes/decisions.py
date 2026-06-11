"""Decision trace API endpoints."""

import json
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["decisions"])

_DATA_DIR = Path("data")


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_decisions(page: int = 1, page_size: int = 50) -> dict:
    """List automatic decisions."""
    now = datetime.now(timezone.utc)
    signals_dir = _DATA_DIR / "paper" / "signals"
    items = []

    if signals_dir.exists():
        for filepath in sorted(
            signals_dir.rglob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(filepath.read_text())
                items.append({
                "decisionId": filepath.stem,
                "strategy": data.get("strategy", "momentum"),
                "signal": data.get("decision", {}).get("action", "unknown"),
                "outcome": data.get("decision", {}).get("action", "unknown"),
                "environment": "local-paper",
                "observedAt": data.get("snapshot", {}).get(
                        "captured_at", now.isoformat()
                ),
                })
            except (json.JSONDecodeError, OSError):
                continue

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": items[start:end],
    }


@router.get("/{decision_id}", dependencies=[Depends(require_api_key)])
async def get_decision(decision_id: str) -> dict:
    """Detail for one automatic decision."""
    now = datetime.now(timezone.utc)
    signals_dir = _DATA_DIR / "paper" / "signals"

    if signals_dir.exists():
        for filepath in signals_dir.rglob(f"{decision_id}*.json"):
            try:
                data = json.loads(filepath.read_text())
                return {
                "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
                "decision": data,
                }
            except (json.JSONDecodeError, OSError):
                continue

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "decision": {
            "decisionId": decision_id,
            "strategy": "",
            "signal": "",
            "outcome": "not_found",
            "environment": "local-paper",
            "observedAt": now.isoformat(),
        },
    }
