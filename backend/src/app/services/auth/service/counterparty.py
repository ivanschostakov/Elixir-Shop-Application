from sqlalchemy.ext.asyncio import AsyncSession
from src.database.crud.auth.user import get_user_by_phone_number
from src.database.models.auth.user import User
from src.integrations.moysklad import MoySkladClient, get_moysklad_client
from src.normalize import coerce_uuid, normalize_email, normalize_phone, optional_str
from .common import logger


async def _get_counterparty_for_phone(phone_number: str, moysklad_client: MoySkladClient) -> dict[str, object] | None:
    if not moysklad_client.is_configured(): return None
    row = await moysklad_client.get_counterparty_by_phone(phone_number)
    return row if isinstance(row, dict) else None


async def _resolve_user_for_phone(db: AsyncSession, phone_number: str, moysklad_client: MoySkladClient,) -> tuple[User | None, dict[str, object] | None]:
    user = await get_user_by_phone_number(db, phone_number)
    counterparty = await _get_counterparty_for_phone(phone_number, moysklad_client)
    if user is not None and user.is_active: return user, counterparty
    return None, counterparty


async def _link_moysklad_counterparty_by_email(user: User, db: AsyncSession) -> None:
    linked_id = user.moysklad_counterparty_id
    local_phone = optional_str(getattr(user, "phone_number", None))
    if linked_id is not None and local_phone: return

    email = normalize_email(user.email)
    if linked_id is None and not email: return

    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return

    try: counterparty = (await moysklad_client.get_counterparty(linked_id) if linked_id is not None else await moysklad_client.get_counterparty_by_email(email))
    except Exception:
        logger.exception(
            "Failed to load MoySklad contact during authentication user_id=%s",
            user.id,
        )
        return

    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None
    if counterparty_id is None: return
    if linked_id is not None and counterparty_id != linked_id:
        logger.warning("MoySklad returned a different linked contact; synchronization skipped user_id=%s", user.id)
        return

    phone = normalize_phone(local_phone)
    remote_phone = normalize_phone(counterparty.get("phone"))
    if phone and remote_phone and not moysklad_client._counterparty_phone_matches(counterparty, phone):
        logger.warning("MoySklad email link has a conflicting phone; manual review required user_id=%s", user.id)
        return

    try:
        import_phone = None
        if not local_phone and remote_phone:
            digits = remote_phone.removeprefix("+")
            if digits.isascii() and digits.isdigit() and 7 <= len(digits) <= 15:
                owner = await get_user_by_phone_number(db, remote_phone)
                if owner is None or owner.id == user.id: import_phone = remote_phone
                else: logger.warning("MoySklad phone belongs to another app account; import skipped user_id=%s", user.id)
        if linked_id is not None and import_phone is None: return
        if import_phone is not None: user.phone_number = import_phone
        if linked_id is None: user.moysklad_counterparty_id = counterparty_id
        await db.commit()
        await db.refresh(user)
    except Exception:
        await db.rollback()
        await db.refresh(user)
        logger.exception(
            "Failed to save MoySklad contact synchronization during authentication user_id=%s",
            user.id,
        )


def _sync_phone_identity_from_counterparty(user: User, *, phone_number: str, counterparty: dict[str, object] | None) -> bool:
    changed = False
    if normalize_phone(user.phone_number) != phone_number:
        user.phone_number = phone_number
        changed = True

    counterparty_id = coerce_uuid(counterparty.get("id")) if isinstance(counterparty, dict) else None
    if counterparty_id is not None and user.moysklad_counterparty_id is None:
        user.moysklad_counterparty_id = counterparty_id
        changed = True

    return changed
