"""FastAPI application factory for the quant-system web console.

The app serves two concerns under one process:
* Read-only JSON API at ``/api/v1/*``
* HTML pages at ``/*`` (Jinja2 templates + HTMX)

No mutation endpoints exist. No order, scheduler, or configuration
mutation is possible through the web console.

"""

from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from quant.api.auth import (
    AccessLoggingMiddleware,
    SecureHeadersMiddleware,
)
from quant.api.routes import router as api_router

_PACKAGE_DIR = Path(__file__).resolve().parent
_TEMPLATE_DIR = _PACKAGE_DIR / "templates"
_STATIC_DIR = _PACKAGE_DIR / "static"
_TEMPLATES = Jinja2Templates(directory=str(_TEMPLATE_DIR))


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

    app.add_middleware(AccessLoggingMiddleware)
    app.add_middleware(SecureHeadersMiddleware)

    app.include_router(api_router)

    def render_page(request: Request, template: str, active: str):
        return _TEMPLATES.TemplateResponse(
            request=request,
            name=template,
            context={
                "active": active,
                "csp_nonce": request.state.csp_nonce,
            },
        )

    @app.get("/")
    async def index() -> RedirectResponse:
        return RedirectResponse("/overview")

    @app.get("/overview")
    async def overview_page(request: Request):
        return render_page(request, "overview.html", "overview")

    @app.get("/accounts")
    async def accounts_page(request: Request):
        return render_page(request, "accounts.html", "accounts")

    @app.get("/health")
    async def health_page(request: Request):
        return render_page(request, "overview.html", "overview")

    @app.get("/operations")
    async def operations_page(request: Request):
        return render_page(request, "operations.html", "operations")

    @app.get("/decisions")
    async def decisions_page(request: Request):
        return render_page(request, "decisions.html", "decisions")

    @app.get("/knowledge")
    async def knowledge_page(request: Request):
        return render_page(request, "knowledge.html", "knowledge")

    @app.get("/system")
    async def system_page(request: Request):
        return render_page(request, "system.html", "system")

    @app.get("/incidents")
    async def incidents_page(request: Request):
        return render_page(request, "incidents.html", "incidents")

    @app.get("/history")
    async def history_page(request: Request):
        return render_page(request, "history.html", "history")

    @app.get("/research")
    async def research_page(request: Request):
        return render_page(request, "research.html", "research")

    app.mount(
        "/static",
        StaticFiles(directory=str(_STATIC_DIR)),
        name="static",
    )

    return app


app = _create_app()
