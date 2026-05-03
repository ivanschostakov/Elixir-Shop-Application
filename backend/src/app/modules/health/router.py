import logging

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.services.cache import get_cache_service
from src.database import get_db

log = logging.getLogger(__name__)

health_router = APIRouter(prefix="/health", tags=["health"])


@health_router.get("/live")
async def health_liveness() -> dict[str, str]:
    return {"status": "ok"}


@health_router.get("/ready")
async def health_readiness(db: AsyncSession = Depends(get_db)) -> JSONResponse:
    checks = {"database": "down", "redis": "down"}
    ready = True

    try:
        await db.execute(text("SELECT 1"))
        checks["database"] = "up"

    except Exception:
        ready = False
        log.exception("health_database_check_failed")

    try:
        cache_client = get_cache_service().client
        if cache_client is None: raise RuntimeError("cache client is not connected")
        if not bool(await cache_client.ping()): raise RuntimeError("redis ping failed")
        checks["redis"] = "up"

    except Exception:
        ready = False
        log.exception("health_redis_check_failed")

    payload = {"status": "ok" if ready else "degraded", "checks": checks}
    status_code = status.HTTP_200_OK if ready else status.HTTP_503_SERVICE_UNAVAILABLE
    return JSONResponse(payload, status_code=status_code)
