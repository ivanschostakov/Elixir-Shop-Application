from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CreateOrderDraftPayload, UpdateOrderDraftPayload
from src.app.services.orders.draft_serialization import serialize_order_draft, serialize_order_drafts
from src.app.services.orders.drafts import (
    create_order_draft_for_user,
    delete_order_draft_for_user,
    get_latest_order_draft_for_checkout,
    get_order_draft_checkout_options_for_user,
    get_order_draft_for_user,
    get_recent_order_drafts_for_user,
    update_order_draft_for_user,
)
from src.app.services.customer_intelligence import record_customer_event_safe
from src.database import get_db
from src.database.models import User
from src.database.schemas import OrderDraftCheckoutOptionsRead, OrderDraftRead

my_order_drafts_router = APIRouter(prefix="/order-drafts", tags=["my_order_drafts"])


@my_order_drafts_router.post("", response_model=OrderDraftRead, status_code=status.HTTP_201_CREATED)
async def create_my_order_draft(payload: CreateOrderDraftPayload, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftRead:
    draft = await create_order_draft_for_user(db, user=current_user, payload=payload)
    await record_customer_event_safe(
        db,
        user_id=current_user.id,
        event_name="checkout_started",
        entity_type="order_draft",
        entity_id=draft.id,
        properties={"items_count": draft.items_count, "total_quantity": draft.total_quantity},
        commit=True,
    )
    return await serialize_order_draft(request, db, draft)


@my_order_drafts_router.get("", response_model=list[OrderDraftRead], status_code=status.HTTP_200_OK)
async def list_my_order_drafts(request: Request, limit: int = Query(default=6, ge=1, le=100), offset: int = Query(default=0, ge=0), created_from: datetime | None = Query(default=None), created_to: datetime | None = Query(default=None), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[OrderDraftRead]:
    drafts = await get_recent_order_drafts_for_user(db, user_id=current_user.id, limit=limit, offset=offset, created_from=created_from, created_to=created_to)
    return await serialize_order_drafts(request, db, drafts)


@my_order_drafts_router.get("/latest", response_model=OrderDraftRead, status_code=status.HTTP_200_OK)
async def get_my_latest_order_draft(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftRead:
    draft = await get_latest_order_draft_for_checkout(db, user_id=current_user.id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    return await serialize_order_draft(request, db, draft)


@my_order_drafts_router.get("/{draft_id}/options", response_model=OrderDraftCheckoutOptionsRead, status_code=status.HTTP_200_OK)
async def get_my_order_draft_options(draft_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftCheckoutOptionsRead:
    options = await get_order_draft_checkout_options_for_user(db, user=current_user, draft_id=draft_id)
    if options is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    return options


@my_order_drafts_router.get("/{draft_id}", response_model=OrderDraftRead, status_code=status.HTTP_200_OK)
async def get_my_order_draft(draft_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftRead:
    draft = await get_order_draft_for_user(db, user_id=current_user.id, draft_id=draft_id)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    return await serialize_order_draft(request, db, draft)


@my_order_drafts_router.patch("/{draft_id}", response_model=OrderDraftRead, status_code=status.HTTP_200_OK)
async def update_my_order_draft(draft_id: int, payload: UpdateOrderDraftPayload, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftRead:
    draft = await update_order_draft_for_user(db, user_id=current_user.id, draft_id=draft_id, payload=payload)
    if draft is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
    return await serialize_order_draft(request, db, draft)


@my_order_drafts_router.delete("/{draft_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_my_order_draft(draft_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> None:
    deleted = await delete_order_draft_for_user(db, user_id=current_user.id, draft_id=draft_id)
    if not deleted: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order draft not found")
