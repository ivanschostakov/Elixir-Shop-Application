import secrets
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status
from src.database.crud import create_delivery_recipient, get_delivery_recipient_by_fields, get_order_by_code
from src.database.models import Order, User
from src.database.schemas import DeliveryRecipientCreate
from src.app.services.orders.common import _normalize_phone
from .common import ORDER_CODE_ALPHABET


async def _generate_order_code(session: AsyncSession) -> str:
    for _ in range(20):
        suffix = "".join(secrets.choice(ORDER_CODE_ALPHABET) for _ in range(8))
        order_code = f"EP-{suffix}"
        if await get_order_by_code(session, order_code) is None: return order_code
    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to generate order code")


async def _get_or_create_self_recipient(session: AsyncSession, *, user: User):
    phone = _normalize_phone(user.phone_number) or ""
    email = (user.email or "").strip().lower()
    recipient = await get_delivery_recipient_by_fields(session, user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email)
    if recipient is not None: return recipient
    return await create_delivery_recipient(session, DeliveryRecipientCreate(user_id=user.id, name=user.name, surname=user.surname, phone=phone, email=email), commit=False)


async def _clear_order_draft_references(session: AsyncSession, *, draft_id: int) -> None:
    linked_orders = list((await session.execute(select(Order).where(Order.draft_id == draft_id))).scalars().all())
    if not linked_orders: return

    for linked_order in linked_orders:
        linked_order.draft = None
        linked_order.draft_id = None

    await session.flush()
