from fastapi.routing import APIRouter

from zentro.intelligence_manager import endpoints as intelligence
from zentro.project_manager import endpoints as projects
from zentro.auth import auth_router
from zentro.web.api import echo, monitoring, rabbit, redis

api_router = APIRouter()
api_router.include_router(monitoring.router)
api_router.include_router(auth_router, tags=["authentication"])
api_router.include_router(echo.router, prefix="/echo", tags=["echo"])
api_router.include_router(redis.router, prefix="/redis", tags=["redis"])
api_router.include_router(rabbit.router, prefix="/rabbit", tags=["rabbit"])
api_router.include_router(projects.router, prefix="/projects", tags=["projects"])
# api_router.include_router(intelligence.router, prefix="/ai", tags=["AI"])
