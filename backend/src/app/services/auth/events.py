from uuid import NAMESPACE_URL, uuid4, uuid5

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import UserEvent

REGISTRATION = "registration_completed"
LOGIN = "login_completed"


async def record_auth_event(db: AsyncSession, user_id: int, *, registration: bool) -> None:
    # Commit with the caller's verification or sign-in, never ahead of it.
    key = uuid5(NAMESPACE_URL, f"elixir:registration:{user_id}") if registration else uuid4()
    await db.execute(
        insert(UserEvent).values(
            user_id=user_id, event_name=REGISTRATION if registration else LOGIN,
            event_id=key, source="api", occurred_at=ufa_now(),
        ).on_conflict_do_nothing(index_elements=[UserEvent.event_id])
    )
