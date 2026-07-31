from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, cast

from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import ReferralProfile, User
from src.normalize import optional_str

from .profile import get_or_create_referral_profile

RewardProgram = Literal["combined"]
UNIFIED_REWARD_PROGRAM: RewardProgram = "combined"
LEGACY_REWARD_PROGRAMS = frozenset(("bonus", "partner", "combined"))


def normalize_reward_program(value: str | None) -> RewardProgram | None:
    normalized = optional_str(value)
    if normalized not in LEGACY_REWARD_PROGRAMS:
        return None
    return cast(RewardProgram, UNIFIED_REWARD_PROGRAM)


async def ensure_unified_reward_program(
    db: AsyncSession,
    *,
    user: User,
) -> ReferralProfile:
    profile = await get_or_create_referral_profile(db, user=user)
    if profile.reward_program != UNIFIED_REWARD_PROGRAM:
        profile.reward_program = UNIFIED_REWARD_PROGRAM
        profile.reward_program_selected_at = (
            profile.reward_program_selected_at or datetime.now(timezone.utc)
        )
        profile.reward_program_selection_source = "system_unified"
    await db.flush()
    return profile


async def select_reward_program(
    db: AsyncSession,
    *,
    user: User,
    program: str,
    source: str = "user",
    force: bool = False,
    reason: str | None = None,
    selected_by_admin_user_id: int | None = None,
) -> ReferralProfile:
    """Compatibility shim for mobile clients released before the programs were unified."""
    del program, source, force, reason, selected_by_admin_user_id
    return await ensure_unified_reward_program(db, user=user)
