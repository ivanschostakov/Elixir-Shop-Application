import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn import Config, Server

from config import CORS_ALLOWED_ORIGINS
from src.app.services.cache import get_cache_service
from .router import api_router
from ..integrations.bitrix import get_bitrix_sync_api_client
from ..integrations.ai import get_professor_client
from ..integrations.website_identity import get_website_identity_client
from ..integrations.delivery.geo import get_geo_client
from ..integrations.delivery.cdek import get_cdek_client
from ..integrations.moysklad import get_moysklad_catalog_client

logger = logging.getLogger("app")
HOST = "0.0.0.0"
PORT = 8000


@asynccontextmanager
async def lifespan(_: FastAPI):
    await get_cache_service().connect()
    try: yield
    finally:
        await get_bitrix_sync_api_client().aclose()
        await get_website_identity_client().aclose()
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
app.mount("/media", StaticFiles(directory="media"), name="media")
app.include_router(api_router)


@app.get("/")
async def read_root() -> dict[str, str]: return {"message": "Elixir Peptide API is running"}


@app.get("/health")
async def healthcheck() -> dict[str, str]: return {"status": "ok"}


async def run_app():
    server = Server(Config(app, host=HOST, port=PORT, reload=False, log_config=None))
    await server.serve()
    logger.warning("uvicorn server stopped")
