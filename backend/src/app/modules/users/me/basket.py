from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.services.recommendations import record_cart_add
from src.app.modules.users.me.schemas import UpdateOrderDraftPayload
from src.app.services.basket import (
    _ensure_basket,
    _get_serialized_basket,
    _get_variant_for_update,
    get_basket_checkout_options_for_user,
    restore_order_draft_to_basket,
    update_basket_checkout_for_user,
)
from src.database import get_db
from src.database.crud import clear_basket, create_basket_item, delete_basket_item, get_basket_item_by_id, update_basket_item
from src.database.crud.basket.basket_item import get_basket_item_by_basket_and_variant
from src.database.models import User
from src.database.schemas import BasketItemCreate, BasketItemUpdate, BasketRead, OrderDraftCheckoutOptionsRead

my_basket_router = APIRouter(prefix="/basket", tags=["my_basket"])


@my_basket_router.get("", response_model=BasketRead, status_code=status.HTTP_200_OK)
async def get_my_basket(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead: return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.post("", response_model=BasketRead, status_code=status.HTTP_200_OK)
async def create_my_basket(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead: return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.post("/items", response_model=BasketRead, status_code=status.HTTP_200_OK)
async def create_my_basket_item(payload: BasketItemCreate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead:
    basket = await _ensure_basket(db, current_user.id)
    variant = await _get_variant_for_update(db, payload.variant_id)
    if variant is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")

    existing_item = await get_basket_item_by_basket_and_variant(db, basket.id, variant.id, user_id=current_user.id)
    next_quantity = payload.quantity if existing_item is None else existing_item.quantity + payload.quantity
    if next_quantity > variant.stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity exceeds available stock")

    await create_basket_item(db, basket_id=basket.id, user_id=current_user.id, product_id=variant.product_id, variant_id=variant.id, quantity=payload.quantity, price=variant.price)
    await record_cart_add( db, user_id=current_user.id, product_id=variant.product_id, quantity=payload.quantity)
    return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.patch("/items/{item_id}", response_model=BasketRead)
async def update_my_basket_item(item_id: int, payload: BasketItemUpdate, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead:
    basket = await _ensure_basket(db, current_user.id)
    basket_item = await get_basket_item_by_id(db, item_id, basket_id=basket.id, user_id=current_user.id)
    if basket_item is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Basket item not found")

    variant = await _get_variant_for_update(db, basket_item.variant_id)
    if variant is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    if payload.quantity > variant.stock: raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Requested quantity exceeds available stock")

    quantity_delta = payload.quantity - basket_item.quantity
    await update_basket_item(db, basket_item, basket_id=basket.id, user_id=current_user.id, product_id=variant.product_id, quantity=payload.quantity, price=variant.price)
    if quantity_delta > 0: await record_cart_add(db, user_id=current_user.id, product_id=variant.product_id, quantity=quantity_delta)
    return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.delete("/items/{item_id}", response_model=BasketRead)
async def delete_my_basket_item(item_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead:
    basket = await _ensure_basket(db, current_user.id)
    basket_item = await get_basket_item_by_id(db, item_id, basket_id=basket.id, user_id=current_user.id)
    if basket_item is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Basket item not found")
    await delete_basket_item(db, basket_item)
    return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.delete("/items", response_model=BasketRead)
async def clear_my_basket(request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead:
    basket = await _ensure_basket(db, current_user.id)
    await clear_basket(db, basket.id)
    return await _get_serialized_basket(request, db, current_user.id)


@my_basket_router.get("/checkout/options", response_model=OrderDraftCheckoutOptionsRead, status_code=status.HTTP_200_OK)
async def get_my_basket_checkout_options(db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> OrderDraftCheckoutOptionsRead: return await get_basket_checkout_options_for_user(db, user=current_user)


@my_basket_router.patch("/checkout", response_model=BasketRead, status_code=status.HTTP_200_OK)
async def update_my_basket_checkout(payload: UpdateOrderDraftPayload, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead: return await update_basket_checkout_for_user(request, db, user=current_user, payload=payload)


@my_basket_router.post("/restore-draft/{draft_id}", response_model=BasketRead, status_code=status.HTTP_200_OK)
async def restore_my_basket_from_draft(draft_id: int, request: Request, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> BasketRead: return await restore_order_draft_to_basket(request, db, user_id=current_user.id, draft_id=draft_id)
