import logging
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from starlette.middleware.cors import CORSMiddleware
from src.app.services.ai.private_attachments import PublicMediaFiles, migrate_legacy_ai_files
from uvicorn import Config, Server

from config import CORS_ALLOWED_ORIGINS
from src.app.services.cache import get_cache_service
from src.app.services.platform_availability import CATALOG_VARY
from .router import api_router
from ..integrations.ai import get_professor_client
from ..integrations.delivery.geo import get_geo_client
from ..integrations.delivery.cdek import get_cdek_client
from ..integrations.moysklad import get_moysklad_catalog_client

logger = logging.getLogger("app")
HOST = "0.0.0.0"
PORT = 8000


@asynccontextmanager
async def lifespan(_: FastAPI):
    from config import ATTACHMENTS_DIR, LEGACY_PUBLIC_AI_ATTACHMENTS_DIR
    await asyncio.to_thread(migrate_legacy_ai_files, LEGACY_PUBLIC_AI_ATTACHMENTS_DIR, ATTACHMENTS_DIR)
    await get_cache_service().connect()
    try: yield
    finally:
        await get_geo_client().aclose()
        await get_cdek_client().aclose()
        await get_professor_client().aclose()
        await get_moysklad_catalog_client().aclose()
        await get_cache_service().close()


app = FastAPI(title="Elixir Peptide API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/media", PublicMediaFiles(directory="media"), name="media")
app.include_router(api_router)


@app.middleware("http")
async def media_cache_control(request: Request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/v1/"):
        cache_control = response.headers.get("Cache-Control", "")
        if "no-store" not in {part.strip().lower() for part in cache_control.split(",")}:
            response.headers["Cache-Control"] = f"{cache_control}, no-store" if cache_control else "no-store"
        existing_vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{existing_vary}, {CATALOG_VARY}" if existing_vary else CATALOG_VARY
    if request.url.path == "/api/v1/app-version":
        response.headers["Cache-Control"] = "no-store"
    if not request.url.path.startswith("/media/"):
        return response

    if response.status_code != 200:
        return response

    # Versioned media can be cached for longer; non-versioned media still gets short CDN/browser cache.
    if request.query_params.get("v"):
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    else:
        response.headers["Cache-Control"] = "public, max-age=86400"
    return response


@app.get("/")
async def read_root() -> dict[str, str]: return {"message": "Elixir Peptide API is running"}


@app.get("/health")
async def healthcheck() -> dict[str, str]: return {"status": "ok"}


async def run_app():
    server = Server(Config(app, host=HOST, port=PORT, reload=False, log_config=None))
    await server.serve()
    logger.warning("uvicorn server stopped")
