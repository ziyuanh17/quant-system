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

from quant.api.models import (
    ApiRootResponse,
)

# Directory containing this file — used for static file paths.
_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR / "static"


def _create_app() -> FastAPI:
     """Create and configure the FastAPI application."""
    app = FastAPI(
        title="Quant System Console",
        description=(
             "Read-only operations, research, and knowledge console for "
             "the quant-system trading platform."
         ),
        version="0.1.0",
     )

      # --- API routes ---

     @app.get("/api/v1", response_model=ApiRootResponse)
    async def api_root() -> ApiRootResponse:
        return ApiRootResponse()

     # --- HTML routes ---

     @app.get("/")
    async def index():
        return FileResponse(_STATIC_DIR / "index.html")

     @app.get("/overview")
    async def overview_page():
        return FileResponse(_TEMPLATE_DIR / "overview.html")

     @app.get("/health")
    async def health_page():
        return FileResponse(_TEMPLATE_DIR / "overview.html")

      # --- Static files ---

    app.mount(
         "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
     )

    return app


app = _create_app()
