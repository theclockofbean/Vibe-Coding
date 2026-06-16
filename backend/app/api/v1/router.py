"""API v1 router."""

from fastapi import APIRouter

from app.api.v1.agent import router as agent_router
from app.api.v1.evaluation import router as evaluation_router
from app.api.v1.handoff import router as handoff_router
from app.api.v1.health import router as health_router
from app.api.v1.logistics import router as logistics_router
from app.api.v1.price import router as price_router
from app.api.v1.quality import router as quality_router
from app.api.v1.spec import router as spec_router

api_router = APIRouter(prefix="/api/v1")

api_router.include_router(spec_router)
api_router.include_router(price_router)
api_router.include_router(logistics_router)
api_router.include_router(quality_router, prefix="/quality", tags=["quality"])
api_router.include_router(agent_router)
api_router.include_router(handoff_router)
api_router.include_router(evaluation_router)
api_router.include_router(health_router)
