"""Publish the bundled neutral welcome artwork without altering product banners."""
import asyncio
import json
from pathlib import Path
import shutil

from sqlalchemy import select

from config import MEDIA_DIR
from src.app.services.cache import get_cache_service
from src.database import SessionLocal, engine
from src.database.crud.catalog.banner import CATALOG_BANNER_LINK, UNIVERSAL_BANNER_AUDIENCE
from src.database.models import Banner


async def main():
    source = Path(__file__).resolve().parents[2] / "assets/banners/welcome-elixirpeptide-v2.jpg"
    image_path = "/media/banners/welcome-elixirpeptide-v2.jpg"
    target = MEDIA_DIR / "banners" / source.name
    if not source.is_file():
        raise FileNotFoundError(source)
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, target)
    target.chmod(0o644)
    async with SessionLocal() as db:
        banner = await db.scalar(select(Banner).where(Banner.image_path.in_(
            [image_path, "/media/banners/welcome-elixirpeptide-v1.png"]
        )).order_by(Banner.id).limit(1))
        if banner is None:
            banner = Banner(image_path=image_path)
            db.add(banner)
        banner.image_path = image_path
        banner.title = "Добро пожаловать в ElixirPeptide"
        banner.inner_link = CATALOG_BANNER_LINK
        banner.outer_link = None
        banner.priority = 1100
        banner.status = "published"
        banner.archived = False
        banner.starts_at = None
        banner.ends_at = None
        banner.audience_json = dict(UNIVERSAL_BANNER_AUDIENCE)
        await db.commit()
        print(json.dumps({"id": banner.id, "image_path": image_path, "inner_link": banner.inner_link, "status": banner.status, "universal": True}))
    await get_cache_service().bump_namespace("banners")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
