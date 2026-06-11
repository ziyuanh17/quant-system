"""Documentation API endpoints.."""

from pathlib import Path

from fastapi import APIRouter

from quant.web.docs_index import build_docs_index, render_doc

router = APIRouter(tags=["docs"])


@router.get("/")
async def list_docs(collection: str = "", search: str = "") -> dict:
    """List documentation documents.."""
    manifest = build_docs_index()
    docs = manifest.docs

    if collection:
        docs = [d for d in docs if d.collection == collection]
    if search:
        search_lower = search.lower()
        docs = [
            d for d in docs
            if search_lower in d.title.lower() or search_lower in d.summary.lower()
        ]

    return {
        "schema": {"schemaVersion": manifest.schema_version, "generatedAt": manifest.generated_at.isoformat()},
        "docs": [d.to_dict() for d in docs],
        "collections": list(manifest.collections),
    }


@router.get("/{slug}")
async def get_doc(slug: str) -> dict:
    """Detail for one documentation document.."""
    doc = render_doc(slug)
    if "error" in doc:
        return {"error": doc["error"]}

    return {
        "schema": {"schemaVersion": "v1", "generatedAt": doc.get("lastModified", "")},
        "document": doc,
    }
