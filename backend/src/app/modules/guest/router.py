from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.schemas.responses import AuthUserRead
from src.app.modules.guest.schemas import (
    GuestBasketQuotePayload,
    GuestBasketQuoteRead,
    GuestPhoneCheckPayload,
    GuestPhoneCheckResponse,
    GuestOrderPayload,
    GuestOrderResponse,
)
from src.app.services.guest_checkout import create_guest_order, quote_guest_basket
from src.app.services.orders.serialization import serialize_order
from src.app.services.rate_limit import client_ip_from_request, enforce_rate_limit
from src.app.services.security import create_access_token
from src.app.services.security.refresh import create_refresh_token, hash_refresh_token
from src.database import get_db
from src.database.crud.auth.user import get_user_by_phone_number
from src.database.crud.auth.user_session import create_user_session
from src.database.schemas.auth.user_session import UserSessionCreate

guest_router = APIRouter(prefix="/guest", tags=["guest"])


async def _guest_rate_limit(request: Request, *, scope: str, principal: str | None = None) -> None:
    key = f"{client_ip_from_request(request)}:{(principal or '').strip().lower()}"
    await enforce_rate_limit(request, scope=scope, limit=30, window_seconds=60, key=key)


@guest_router.post("/basket/quote", response_model=GuestBasketQuoteRead, status_code=status.HTTP_200_OK)
async def quote_guest_basket_route(payload: GuestBasketQuotePayload, request: Request, db: AsyncSession = Depends(get_db)) -> GuestBasketQuoteRead:
    await _guest_rate_limit(request, scope="guest:basket_quote")
    return await quote_guest_basket(db, request, payload.items)


@guest_router.post("/phone/check", response_model=GuestPhoneCheckResponse, status_code=status.HTTP_200_OK)
async def check_guest_phone(payload: GuestPhoneCheckPayload, request: Request, db: AsyncSession = Depends(get_db)) -> GuestPhoneCheckResponse:
    await _guest_rate_limit(request, scope="guest:phone_check", principal=payload.phone_number)
    existing_user = await get_user_by_phone_number(db, payload.phone_number)
    return GuestPhoneCheckResponse(phone_number=payload.phone_number, exists=bool(existing_user and existing_user.is_active))


@guest_router.post("/orders", response_model=GuestOrderResponse, status_code=status.HTTP_201_CREATED)
async def create_guest_order_route(payload: GuestOrderPayload, request: Request, db: AsyncSession = Depends(get_db)) -> GuestOrderResponse:
    await _guest_rate_limit(request, scope="guest:orders", principal=payload.recipient.phone)
    user, order = await create_guest_order(db, request, payload)

    refresh_token = create_refresh_token()
    session = await create_user_session(db, UserSessionCreate(user_id=user.id, refresh_token_hash=hash_refresh_token(refresh_token)))
    access_token = create_access_token(user_id=user.id, session_id=session.id)

    return GuestOrderResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        session_id=session.id,
        user=AuthUserRead.model_validate(user),
        order=await serialize_order(request, db, order),
    )
