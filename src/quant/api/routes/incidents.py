"""Incident API endpoints.

Provides incident listing and detail views.

"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["incidents"])


@router.get("/")
async def list_incidents(status: str = "all") -> dict:
     """List active and resolved incidents.

      Returns
      -------
      dict
          Incident lists.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "active": [],
          "resolved": [],
       }


@router.get("/{incident_id}")
async def get_incident(incident_id: str) -> dict:
     """Detail for one incident.

      Returns
      -------
      dict
          Full incident detail with timeline and evidence.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "incident": {
               "incidentId": incident_id,
               "title": "",
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
