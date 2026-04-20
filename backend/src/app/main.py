import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn import Config, Server

from .router import api_router
from ..integrations.bitrix import get_bitrix_sync_api_client
from ..integrations.website_identity import get_website_identity_client
from ..integrations.delivery.geo import get_geo_client
from ..integrations.delivery.cdek import get_cdek_client

logger = logging.getLogger("app")
HOST = "0.0.0.0"
PORT = 8000

@asynccontextmanager
async def lifespan(_: FastAPI):
    try: yield
    finally:
        await get_bitrix_sync_api_client().aclose()
        await get_website_identity_client().aclose()
        await get_geo_client().aclose()
        await get_cdek_client().aclose()


app = FastAPI(title="Elixir Shop API", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=False, allow_methods=["*"], allow_headers=["*"])
app.mount("/media", StaticFiles(directory="media"), name="media")
app.include_router(api_router)


@app.get("/")
async def read_root() -> dict[str, str]: return {"message": "Elixir Shop API is running"}


@app.get("/health")
async def healthcheck() -> dict[str, str]: return {"status": "ok"}


async def run_app():
    server = Server(Config(app, host=HOST, port=PORT, reload=False, log_config=None))
    await server.serve()
    logger.warning("uvicorn server stopped")
