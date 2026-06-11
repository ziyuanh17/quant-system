"""API route registration.

All API endpoints are defined as FastAPI routers and mounted under
``/api/v1`` in the application factory.

"""

from fastapi import APIRouter

from quant.api.routes.root import router as root_router

router = APIRouter(prefix="/api/v1")
router.include_router(root_router, tags=["root"])
