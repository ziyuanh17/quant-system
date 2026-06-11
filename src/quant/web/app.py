"""FastAPI application factory for the quant-system web console.

The app serves two concerns under one process:
* Read-only JSON API at ``/api/v1/*``
* HTML pages at ``/*`` (Jinja2 templates + HTMX)

No mutation endpoints exist. No order, scheduler, or configuration
mutation is possible through the web console.

"""

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from quant.api.auth import (
    AccessLoggingMiddleware,
    SecureHeadersMiddleware,
)
from quant.api.routes import router as api_router

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR / "static"


def _create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Quant System Console",
        description=(
            "Read-only operations, research, and knowledge console for "
            "the quant-system trading platform.",
        ),
        version="0.1.0",
    )

    app.add_middleware(AccessLoggingMiddleware)
    app.add_middleware(SecureHeadersMiddleware)

    app.include_router(api_router)

    @app.get("/")
    async def index():
        return FileResponse(_STATIC_DIR / "index.html")

    @app.get("/overview")
    async def overview_page():
        return FileResponse(_TEMPLATE_DIR / "overview.html")

    @app.get("/accounts")
    async def accounts_page():
        return FileResponse(_TEMPLATE_DIR / "accounts.html")

    @app.get("/health")
    async def health_page():
        return FileResponse(_TEMPLATE_DIR / "overview.html")

    @app.get("/operations")
    async def operations_page():
         return FileResponse(_TEMPLATE_DIR / "operations.html")

    @app.get("/decisions")
    async def decisions_page():
         return FileResponse(_TEMPLATE_DIR / "decisions.html")

    @app.get("/knowledge")
    async def knowledge_page():
         return FileResponse(_TEMPLATE_DIR / "knowledge.html")

    @app.get("/system")
    async def system_page():
         return FileResponse(_TEMPLATE_DIR / "system.html")

    @app.get("/incidents")
    async def incidents_page():
         return FileResponse(_TEMPLATE_DIR / "incidents.html")

    @app.get("/history")
    async def history_page():
        return FileResponse(_TEMPLATE_DIR / "history.html")

    @app.get("/research")
    async def research_page():
         return FileResponse(_TEMPLATE_DIR / "research.html")

    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    return app


app = _create_app()
