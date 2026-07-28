from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PresenceHeartbeatResponse(BaseModel):
    ok: Literal[True] = True
    seen_at: datetime
