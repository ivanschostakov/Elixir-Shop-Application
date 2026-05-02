import asyncio
import logging
from contextlib import suppress
from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.staticfiles import StaticFiles
from uvicorn import Config, Server

from config import NOTIFICATION_SCAN_INTERVAL_MINUTES, NOTIFICATIONS_ENABLED, ONEC_SYNC_ENABLED, ONEC_SYNC_INTERVAL_MINUTES
from src.app.services.cache import get_cache_service
from src.app.services.notifications import run_notification_processors_once
from src.database import get_session
from .router import api_router
from ..integrations.bitrix import get_bitrix_sync_api_client
from ..integrations.ai.client import get_professor_client
from ..integrations.website_identity import get_website_identity_client
from ..integrations.delivery.geo import get_geo_client
from ..integrations.delivery.cdek import get_cdek_client
from ..integrations.onec import get_onec_catalog_client, sync_onec_product_catalog

logger = logging.getLogger("app")
HOST = "0.0.0.0"
PORT = 8000


async def _notification_loop(stop_event: asyncio.Event):
    check_interval_seconds = max(NOTIFICATION_SCAN_INTERVAL_MINUTES, 1) * 60
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=check_interval_seconds)
            if stop_event.is_set(): return
        except TimeoutError: pass

        if stop_event.is_set(): return

        try:
            async with get_session() as session: results = await run_notification_processors_once(session)
            logger.info("Notification runner tick completed: %s", results)
        except Exception:
            logger.exception("Notification runner tick failed")


async def _onec_catalog_sync_loop(stop_event: asyncio.Event):
    check_interval_seconds = max(ONEC_SYNC_INTERVAL_MINUTES, 1) * 60
    while not stop_event.is_set():
        try:
            stats = await sync_onec_product_catalog()
            logger.info("1C catalog sync tick completed: %s", stats.as_dict())
        except Exception: logger.exception("1C catalog sync tick failed")

        try: await asyncio.wait_for(stop_event.wait(), timeout=check_interval_seconds)
        except TimeoutError: pass


@asynccontextmanager
async def lifespan(_: FastAPI):
    await get_cache_service().connect()
    notification_stop_event = asyncio.Event()
    notification_task: asyncio.Task | None = None
    onec_sync_stop_event = asyncio.Event()
    onec_sync_task: asyncio.Task | None = None
    if NOTIFICATIONS_ENABLED: notification_task = asyncio.create_task(_notification_loop(notification_stop_event))
    if ONEC_SYNC_ENABLED: onec_sync_task = asyncio.create_task(_onec_catalog_sync_loop(onec_sync_stop_event))

    try: yield
    finally:
        notification_stop_event.set()
        onec_sync_stop_event.set()
        if notification_task is not None:
            notification_task.cancel()
            with suppress(asyncio.CancelledError): await notification_task

        if onec_sync_task is not None:
            onec_sync_task.cancel()
            with suppress(asyncio.CancelledError): await onec_sync_task

        await get_bitrix_sync_api_client().aclose()
        await get_website_identity_client().aclose()
        await get_geo_client().aclose()
        await get_cdek_client().aclose()
        await get_professor_client().aclose()
        await get_onec_catalog_client().aclose()
        await get_cache_service().close()


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
