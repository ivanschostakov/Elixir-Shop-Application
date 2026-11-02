import logging
from sqlalchemy import func, select
from config import COMMUNITY_MEDIA_DIR


log = logging.getLogger(__name__)


async def lock_community_ingest(db, chat_id: int) -> None:
    await db.execute(select(func.pg_advisory_xact_lock(1129270612, func.hashtext(str(chat_id)))))


COMMUNITY_REACTION_EMOJIS = ("👍", "❤️", "🔥", "😂", "👏", "😮", "😢", "🙏")


COMMUNITY_AVATARS_DIR = COMMUNITY_MEDIA_DIR / "avatars"


COMMUNITY_ATTACHMENTS_DIR = COMMUNITY_MEDIA_DIR / "attachments"


COMMUNITY_GROUP_DIR = COMMUNITY_MEDIA_DIR / "group"


for _directory in (COMMUNITY_AVATARS_DIR, COMMUNITY_ATTACHMENTS_DIR, COMMUNITY_GROUP_DIR): _directory.mkdir(parents=True, exist_ok=True)
