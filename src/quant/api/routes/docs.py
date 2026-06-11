"""Documentation API endpoints.

Provides docs listing, search, and individual doc detail.

"""

from datetime import datetime, timezone

from fastapi import APIRouter

router = APIRouter(tags=["docs"])


@router.get("/")
async def list_docs(collection: str = "", search: str = "") -> dict:
     """List documentation documents.

      Returns
      -------
      dict
          Doc list and available collections.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "docs": [],
          "collections": [
               "start_here",
               "operate",
               "safety_and_broker",
               "research_and_data",
               "migration_and_scheduling",
               "incidents_and_rehearsals",
               "project_management",
            ],
       }


@router.get("/{slug}")
async def get_doc(slug: str) -> dict:
     """Detail for one documentation document.

      Returns
      -------
      dict
          Full document with rendered content.

      """
     now = datetime.now(timezone.utc)
     return {
          "schema": {"schemaVersion": "v1", "generatedAt": now.isoformat()},
          "document": {
               "slug": slug,
               "title": "",
               "collection": "",
               "docType": "design",
               "summary": "",
               "toc": [],
               "renderedContent": "",
               "lastModified": None,
               "sourceCommit": None,
               "status": "design",
               "supersededBy": None,
               "relatedComponents": [],
               "relatedDocuments": [],
               "glossaryTerms": [],
            },
       }
