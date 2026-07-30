import logging
from typing import Any

import httpx
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import User
from src.integrations.bitrix_promo import (
    BitrixPromoClient,
    BitrixPromoError,
    bitrix_promo_configured,
)
from src.normalize import optional_str

logger = logging.getLogger(__name__)


async def refresh_assigned_referrer_promo(
    db: AsyncSession,
    *,
    user: User,
    client: BitrixPromoClient | None = None,
) -> dict[str, Any] | None:
    if not bitrix_promo_configured() or not user.email:
        return None

    try:
        response = await (client or BitrixPromoClient()).profile(user_email=user.email)
    except (BitrixPromoError, RuntimeError, httpx.HTTPError):
        logger.exception(
            "Could not refresh assigned Bitrix referrer promo for user_id=%s",
            user.id,
        )
        return None

    program_profile = response.get("program_profile")
    if not isinstance(program_profile, dict) or "referrer_promo" not in program_profile:
        logger.warning(
            "Bitrix profile response is missing referrer_promo for user_id=%s",
            user.id,
        )
        return None

    assigned_promo = optional_str(program_profile.get("referrer_promo"))
    if optional_str(user.promo_code) != assigned_promo:
        user.promo_code = assigned_promo
        await db.flush()

    return program_profile
