import logging
from config import COMMUNITY_MEDIA_DIR


log = logging.getLogger(__name__)


COMMUNITY_REACTION_EMOJIS = ("👍", "❤️", "🔥", "😂", "👏", "😮", "😢", "🙏")


COMMUNITY_AVATARS_DIR = COMMUNITY_MEDIA_DIR / "avatars"


COMMUNITY_ATTACHMENTS_DIR = COMMUNITY_MEDIA_DIR / "attachments"


COMMUNITY_GROUP_DIR = COMMUNITY_MEDIA_DIR / "group"


for _directory in (COMMUNITY_AVATARS_DIR, COMMUNITY_ATTACHMENTS_DIR, COMMUNITY_GROUP_DIR): _directory.mkdir(parents=True, exist_ok=True)
