"""Incident API endpoints."""

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key

router = APIRouter(tags=["incidents"])

_DOCS_DIR = Path("docs")


def _parse_incident_doc(filepath):
    """Parse an incident document and extract metadata."""
    try:
        text = filepath.read_text(encoding="utf-8")
    except OSError:
        return None

    title_match = re.search(r"^# (.+)$", text, re.MULTILINE)
    title = title_match.group(1).strip() if title_match else filepath.stem

    severity = "medium"
    if "critical" in text[:500].lower():
        severity = "critical"
    elif "high" in text[:500].lower():
        severity = "high"

    date_match = re.search(r"(\d{4}-\d{2}-\d{2})", filepath.stem)
    detected_at = date_match.group(1) + "T00:00:00Z" if date_match else None

    is_resolved = "resolved" in text.lower() or "remediation" in text.lower()

    return {
        "incidentId": filepath.stem,
        "title": title,
        "severity": severity,
        "status": "resolved" if is_resolved else "active",
        "detectedAt": detected_at,
        "resolvedAt": detected_at,
        "impactedEnvironments": ["alpaca-paper"],
        "unresolvedActions": 0 if is_resolved else 1,
        "description": text[:500].replace("\n", " "),
        "timeline": [],
        "linkedEvidence": [str(filepath)],
        "linkedDocument": str(filepath.name),
        "unresolvedActionItems": [],
    }


@router.get("/", dependencies=[Depends(require_api_key)])
async def list_incidents(status: str = "all") -> dict:
    """List active and resolved incidents."""
    now = datetime.now(timezone.utc)
    active = []
    resolved = []

    if _DOCS_DIR.exists():
        for filepath in sorted(
            _DOCS_DIR.glob("actionable_paper_order_incident_*.md")
        ):
            incident = _parse_incident_doc(filepath)
            if incident:
                if incident["status"] == "active":
                    active.append(incident)
                else:
                    resolved.append(incident)

    if status == "all":
        active_list = active
        resolved_list = resolved
    elif status == "active":
        active_list = [i for i in active if i["status"] == "active"]
        resolved_list = []
    else:
        active_list = []
        resolved_list = [i for i in resolved if i["status"] == "resolved"]

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "active": active_list,
        "resolved": resolved_list,
    }


@router.get("/{incident_id}", dependencies=[Depends(require_api_key)])
async def get_incident(incident_id: str) -> dict:
    """Detail for one incident."""
    now = datetime.now(timezone.utc)
    filepath = _DOCS_DIR / f"{incident_id}.md"

    if filepath.exists():
        incident = _parse_incident_doc(filepath)
        if incident:
            return {
                "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
                "incident": incident,
            }

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
        "incident": {
            "incidentId": incident_id,
            "title": "Not found",
            "severity": "medium",
            "status": "resolved",
            "description": "",
            "timeline": [],
            "linkedEvidence": [],
            "linkedDocument": None,
            "unresolvedActions": [],
            "impactedEnvironments": [],
        },
    }
