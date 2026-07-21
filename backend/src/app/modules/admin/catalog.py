from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_product, serialize_category
from src.app.modules.admin.schemas import (
    AdminCategoryPayload,
    AdminCategoryRead,
    AdminPage,
    AdminProductMerchandisePayload,
    AdminProductRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.cache import get_cache_service
from src.database import get_db
from src.database.models import Product, ProductByCategory, ProductCategory

admin_catalog_router = APIRouter(tags=["admin_catalog"])


def _product_options():
    return (
        selectinload(Product.variants),
        selectinload(Product.products_by_category),
    )


async def _get_product(db: AsyncSession, product_id: int) -> Product:
    product = (await db.execute(select(Product).options(*_product_options()).where(Product.id == product_id).execution_options(populate_existing=True))).scalar_one_or_none()
    if product is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    return product


async def _bump_catalog_cache() -> None:
    cache = get_cache_service()
    await cache.bump_namespace("catalog")
    await cache.bump_namespace("product")
    await cache.bump_namespace("categories")


@admin_catalog_router.get("/products", response_model=AdminPage[AdminProductRead])
async def list_products(
    request: Request,
    q: str | None = Query(default=None, max_length=100),
    archived: bool | None = None,
    in_stock: bool | None = None,
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminPage[AdminProductRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if archived is not None:
        filters.append(Product.archived.is_(archived))
    if in_stock is not None:
        filters.append(Product.in_stock.is_(in_stock))
    base = select(Product).where(*filters)
    if category_id:
        base = base.join(ProductByCategory).where(ProductByCategory.category_id == category_id)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list((await db.execute(base.options(*_product_options()).order_by(Product.in_stock.desc(), Product.priority.desc(), Product.id.desc()).offset(offset).limit(limit))).scalars().unique().all())
    return AdminPage(items=[serialize_admin_product(request, row) for row in rows], total=total, limit=limit, offset=offset)


@admin_catalog_router.get("/products/{product_id}", response_model=AdminProductRead)
async def get_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminProductRead:
    return serialize_admin_product(request, await _get_product(db, product_id))


@admin_catalog_router.patch("/products/{product_id}/merchandise", response_model=AdminProductRead)
async def update_product_merchandise(
    product_id: int,
    payload: AdminProductMerchandisePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("catalog.merchandise", write=True)),
) -> AdminProductRead:
    product = await _get_product(db, product_id)
    ensure_not_stale(actual=product.updated_at, expected=payload.expected_updated_at)
    if payload.priority > 0 and not product.has_image:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Product needs an image before it can be prioritized")
    category_ids = set(payload.category_ids)
    if category_ids:
        valid_ids = set((await db.execute(select(ProductCategory.id).where(ProductCategory.id.in_(category_ids)))).scalars().all())
        if valid_ids != category_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more categories do not exist")
    before = serialize_admin_product(request, product).model_dump(mode="json")
    product.description = payload.description
    product.usage = payload.usage
    product.expiration = payload.expiration
    product.priority = payload.priority
    existing = {link.category_id: link for link in product.products_by_category}
    for category_id, link in existing.items():
        if category_id not in category_ids:
            await db.delete(link)
    for category_id in category_ids - set(existing):
        db.add(ProductByCategory(product_id=product.id, category_id=category_id))
    await db.flush()
    product = await _get_product(db, product.id)
    after = serialize_admin_product(request, product)
    await add_admin_audit(db, request, context, action="product.merchandise.update", entity_type="product", entity_id=product.id, before=before, after=after.model_dump(mode="json"))
    await db.commit()
    await _bump_catalog_cache()
    return after


@admin_catalog_router.get("/categories", response_model=AdminPage[AdminCategoryRead])
async def list_categories(
    q: str | None = Query(default=None, max_length=100),
    archived: bool | None = None,
    limit: int = Query(default=100, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminPage[AdminCategoryRead]:
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(ProductCategory.name.ilike(pattern), ProductCategory.description.ilike(pattern)))
    if archived is not None:
        filters.append(ProductCategory.archived.is_(archived))
    total = int((await db.execute(select(func.count(ProductCategory.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(ProductCategory).where(*filters).order_by(func.lower(ProductCategory.name), ProductCategory.id).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[serialize_category(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_catalog_router.post("/categories", response_model=AdminCategoryRead, status_code=status.HTTP_201_CREATED)
async def create_category(
    payload: AdminCategoryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("categories.manage", write=True)),
) -> AdminCategoryRead:
    category = ProductCategory(name=payload.name.strip(), description=payload.description, archived=payload.archived)
    db.add(category)
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists") from None
    result = serialize_category(category)
    await add_admin_audit(db, request, context, action="category.create", entity_type="category", entity_id=category.id, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_catalog_cache()
    return result


@admin_catalog_router.put("/categories/{category_id}", response_model=AdminCategoryRead)
async def update_category(
    category_id: int,
    payload: AdminCategoryPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("categories.manage", write=True)),
) -> AdminCategoryRead:
    category = await db.get(ProductCategory, category_id)
    if category is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Category not found")
    before = serialize_category(category).model_dump(mode="json")
    category.name = payload.name.strip()
    category.description = payload.description
    category.archived = payload.archived
    try:
        await db.flush()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Category name already exists") from None
    result = serialize_category(category)
    await add_admin_audit(db, request, context, action="category.update", entity_type="category", entity_id=category.id, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    await _bump_catalog_cache()
    return result
