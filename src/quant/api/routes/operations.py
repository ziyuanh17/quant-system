"""Operations API endpoints."""

import json
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["operations"])

_DATA_DIR = Path("data")


def _scan_json_files(directory: Path) -> list[dict]:
    """Scan a directory for JSON files and parse them."""
    if not directory.exists():
        return []
    items = []
    for filepath in sorted(
        directory.rglob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True
    ):
        try:
            data = json.loads(filepath.read_text())
            data["_source_file"] = str(filepath)
            items.append(data)
        except (json.JSONDecodeError, OSError):
            continue
    return items


@router.get("/runs", dependencies=[Depends(require_api_key)])
async def list_runs(
    run_type: str = "all",
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """List workflow and scheduled runs.."""
    now = datetime.now(UTC)
    items: list[dict] = []

    if run_type in ("all", "workflow"):
        for d in [
            _DATA_DIR / "workflows" / "paper-signal-refresh",
            _DATA_DIR / "workflows" / "alpaca-paper-refresh",
            _DATA_DIR / "workflows" / "dry-run-refresh",
        ]:
            items.extend(_scan_json_files(d))

    if run_type in ("all", "scheduler"):
        for d in [
            _DATA_DIR / "scheduler" / "latest",
            _DATA_DIR / "scheduler" / "dry-run",
        ]:
            items.extend(_scan_json_files(d))

    total = len(items)
    start = (page - 1) * page_size
    end = start + page_size

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "runType": run_type,
        "total": total,
        "page": page,
        "pageSize": page_size,
        "items": items[start:end],
    }


@router.get("/events", dependencies=[Depends(require_api_key)])
async def list_events(
    page: int = 1,
    page_size: int = 50,
) -> dict:
    """List operational events from logs.."""
    now = datetime.now(UTC)
    logs_dir = _DATA_DIR / "logs"
    items: list[dict] = []

    if logs_dir.exists():
        for filepath in sorted(
            logs_dir.rglob("*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        ):
            try:
                data = json.loads(filepath.read_text())
                items.append(
                    {
                        "timestamp": data.get("timestamp", now.isoformat()),
                        "eventType": data.get("event_type", "log"),
                        "component": data.get("component", "logs"),
                        "status": data.get("status", "unknown"),
                        "message": data.get("message", ""),
                        "workflowId": data.get("workflow_id"),
                        "evidenceRef": str(filepath),
                    }
                )
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
