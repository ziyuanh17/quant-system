"""API route registration.

All API endpoints are defined as FastAPI routers and mounted under
``/api/v1`` in the application factory.

Authentication is enforced via ``QUANT_CONSOLE_API_KEY`` when set.
The root endpoint (schema discovery) remains public.

"""

from fastapi import APIRouter, Depends

from quant.api.auth import require_api_key
from quant.api.routes.accounts import router as accounts_router
from quant.api.routes.decisions import router as decisions_router
from quant.api.routes.docs import router as docs_router
from quant.api.routes.history import router as history_router
from quant.api.routes.incidents import router as incidents_router
from quant.api.routes.operations import router as operations_router
from quant.api.routes.research import router as research_router
from quant.api.routes.root import router as root_router
from quant.api.routes.system import router as system_router

router = APIRouter(
    prefix="/api/v1",
    dependencies=[Depends(require_api_key)],
)
router.include_router(root_router, tags=["root"])
router.include_router(accounts_router, prefix="/accounts", tags=["accounts"])
router.include_router(operations_router, prefix="/operations", tags=["operations"])
router.include_router(decisions_router, prefix="/decisions", tags=["decisions"])
router.include_router(docs_router, prefix="/docs", tags=["docs"])
router.include_router(system_router, prefix="/system", tags=["system"])
router.include_router(incidents_router, prefix="/incidents", tags=["incidents"])
router.include_router(research_router, prefix="/research", tags=["research"])
router.include_router(history_router, prefix="/history", tags=["history"])
