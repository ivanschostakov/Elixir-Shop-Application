from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.database import get_db
from src.database.crud import create_product, delete_product, get_product_by_id, get_products, update_product
from src.database.models import User
from src.database.schemas import ProductCreate, ProductUpdate, ProductWithVariantsRead

from .helpers import serialize_product_with_variants, serialize_products_with_variants

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.get("/{product_id}", response_model=ProductWithVariantsRead)
async def products_get_by_id(request: Request, product_id: int, db: AsyncSession = Depends(get_db)):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return serialize_product_with_variants(request, product)


@products_router.get("", response_model=list[ProductWithVariantsRead])
async def products_get(
    request: Request,
    q: str | None = Query(default=None, min_length=1, max_length=100),
    sku: str | None = Query(default=None, min_length=1, max_length=100),
    min_priority: int | None = Query(default=None, ge=0),
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    sort: Literal["newest", "name_asc", "name_desc", "price_asc", "price_desc"] | None = Query(default=None),
): return serialize_products_with_variants(request, await get_products(db, q=q, sku=sku, min_priority=min_priority, category_id=category_id, offset=offset, limit=limit, sort=sort))


@products_router.post("", response_model=ProductWithVariantsRead, status_code=status.HTTP_201_CREATED)
async def products_create(request: Request, data: ProductCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    try:
        product = await create_product(db, data)
        product = await get_product_by_id(db, product.id, include_out_of_stock=True)
        return serialize_product_with_variants(request, product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product with this sku or name already exists")


@products_router.patch("/{product_id}", response_model=ProductWithVariantsRead)
async def products_patch(request: Request, product_id: int, data: ProductUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    product = await get_product_by_id(db, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        updated_product = await update_product(db, product, data)
        updated_product = await get_product_by_id(db, updated_product.id, include_out_of_stock=True)
        return serialize_product_with_variants(request, updated_product)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product with this sku or name already exists")


@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def products_delete(product_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_user)):
    product = await get_product_by_id(db, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await delete_product(db, product)
