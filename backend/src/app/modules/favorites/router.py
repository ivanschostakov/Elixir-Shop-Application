from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.products.helpers import serialize_products
from src.app.services.notifications.core import (
    activate_stock_notifications_for_favourite_product,
    deactivate_stock_notifications_for_favourite_product,
)
from src.database import get_db
from src.database.crud import (
    create_favoured_product,
    delete_favoured_product,
    get_favoured_product_by_user_and_product,
    get_favourite_products_for_user,
    get_product_by_id,
)
from src.database.models import User
from src.database.schemas import FavouredProductCreate, FavouriteProductStatusRead, ProductRead

favourite_products_router = APIRouter(prefix="/products", dependencies=[Depends(get_current_user)])


@favourite_products_router.get("/{product_id}", response_model=FavouriteProductStatusRead)
async def favourite_products_get_status(product_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> FavouriteProductStatusRead:
    favourite = await get_favoured_product_by_user_and_product(db, current_user.id, product_id)
    return FavouriteProductStatusRead(product_id=product_id, is_favoured=favourite is not None)


@favourite_products_router.get("", response_model=list[ProductRead])
async def favourite_products_get(request: Request, user_id: int | None = Query(default=None, ge=1), product_id: int | None = Query(default=None, ge=1), offset: int = Query(default=0, ge=0), limit: int = Query(default=100, ge=1, le=100), db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> list[ProductRead]:
    resolved_user_id = current_user.id if user_id is None else user_id
    if resolved_user_id != current_user.id: raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only access your own favorites")
    return serialize_products(request, await get_favourite_products_for_user(db, resolved_user_id, product_id=product_id, offset=offset, limit=limit))


@favourite_products_router.post("/{product_id}", response_model=FavouriteProductStatusRead, status_code=status.HTTP_201_CREATED)
async def favourite_products_create(product_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)) -> FavouriteProductStatusRead:
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

    favourite = await get_favoured_product_by_user_and_product(db, current_user.id, product_id)
    if favourite is None:
        await create_favoured_product(db, FavouredProductCreate(user_id=current_user.id, product_id=product_id))
        await activate_stock_notifications_for_favourite_product(db, user_id=current_user.id, product_id=product_id)

    return FavouriteProductStatusRead(product_id=product_id, is_favoured=True)


@favourite_products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def favourite_products_delete(product_id: int, db: AsyncSession = Depends(get_db), current_user: User = Depends(get_current_user)):
    favourite = await get_favoured_product_by_user_and_product(db, current_user.id, product_id)
    if favourite is None: return None
    await deactivate_stock_notifications_for_favourite_product(db, user_id=current_user.id, product_id=product_id)
    await delete_favoured_product(db, favourite)
    return None
