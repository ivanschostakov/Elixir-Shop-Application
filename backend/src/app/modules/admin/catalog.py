from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, UploadFile
from sqlalchemy import exists, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.modules.admin.helpers import ensure_not_stale, serialize_admin_product, serialize_category
from src.app.modules.admin.schemas import (
    AdminCatalogStockSettingsPayload,
    AdminCatalogStockSettingsRead,
    AdminCategoryPayload,
    AdminCategoryRead,
    AdminPage,
    AdminProductMerchandisePayload,
    AdminProductRead,
)
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.app.services.cache import get_cache_service
from src.app.services.stock_visibility import (
    CATALOG_SETTINGS_ID,
    get_stock_visibility_policy,
)
from src.app.services.product_image_storage import prepare_product_image, save_product_image
from config import ufa_now
from src.database import get_db
from src.database.models import CatalogSettings, Product, ProductByCategory, ProductCategory, Variant
from src.product_media import product_image_path, variant_image_path

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
    low_stock: bool | None = None,
    category_id: int | None = Query(default=None, ge=1),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminPage[AdminProductRead]:
    stock_policy = await get_stock_visibility_policy(db)
    filters = []
    if q:
        pattern = f"%{q.strip()}%"
        filters.append(or_(Product.name.ilike(pattern), Product.sku.ilike(pattern)))
    if archived is not None:
        filters.append(Product.archived.is_(archived))
    if in_stock is not None:
        filters.append(Product.in_stock.is_(in_stock))
    if low_stock:
        filters.append(exists(select(Variant.id).where(
            Variant.product_id == Product.id,
            Variant.archived.is_(False),
            Variant.stock <= 3,
        )))
    base = select(Product).where(*filters)
    if category_id:
        base = base.join(ProductByCategory).where(ProductByCategory.category_id == category_id)
    total = int((await db.execute(select(func.count()).select_from(base.subquery()))).scalar_one())
    rows = list((await db.execute(base.options(*_product_options()).order_by(Product.in_stock.desc(), Product.priority.desc(), Product.id.desc()).offset(offset).limit(limit))).scalars().unique().all())
    return AdminPage(
        items=[
            serialize_admin_product(request, row, stock_policy=stock_policy)
            for row in rows
        ],
        total=total,
        limit=limit,
        offset=offset,
    )


@admin_catalog_router.get(
    "/products/stock-visibility/settings",
    response_model=AdminCatalogStockSettingsRead,
)
async def get_catalog_stock_settings(
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminCatalogStockSettingsRead:
    settings = await db.get(CatalogSettings, CATALOG_SETTINGS_ID)
    if settings is None:
        return AdminCatalogStockSettingsRead(
            enabled=False,
            reduction=0,
            updated_at=None,
        )
    return AdminCatalogStockSettingsRead(
        enabled=settings.stock_reduction_enabled,
        reduction=settings.stock_reduction,
        updated_at=settings.updated_at,
    )


@admin_catalog_router.put(
    "/products/stock-visibility/settings",
    response_model=AdminCatalogStockSettingsRead,
)
async def update_catalog_stock_settings(
    payload: AdminCatalogStockSettingsPayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(
        require_permission("catalog.merchandise", write=True)
    ),
) -> AdminCatalogStockSettingsRead:
    settings = await db.get(CatalogSettings, CATALOG_SETTINGS_ID)
    if settings is None:
        settings = CatalogSettings(id=CATALOG_SETTINGS_ID)
        db.add(settings)
        before = None
    else:
        before = {
            "enabled": settings.stock_reduction_enabled,
            "reduction": settings.stock_reduction,
        }
    settings.stock_reduction_enabled = payload.enabled
    settings.stock_reduction = payload.reduction
    await db.flush()
    result = AdminCatalogStockSettingsRead(
        enabled=settings.stock_reduction_enabled,
        reduction=settings.stock_reduction,
        updated_at=settings.updated_at,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="catalog.stock_visibility.update",
        entity_type="catalog_settings",
        entity_id=CATALOG_SETTINGS_ID,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    await _bump_catalog_cache()
    return result


@admin_catalog_router.get("/products/{product_id}", response_model=AdminProductRead)
async def get_product(
    product_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("catalog.read")),
) -> AdminProductRead:
    return serialize_admin_product(
        request,
        await _get_product(db, product_id),
        stock_policy=await get_stock_visibility_policy(db),
    )


@admin_catalog_router.patch("/products/{product_id}/merchandise", response_model=AdminProductRead)
async def update_product_merchandise(
    product_id: int,
    payload: AdminProductMerchandisePayload,
    request: Request,
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("catalog.merchandise", write=True)),
) -> AdminProductRead:
    product = await _get_product(db, product_id)
    stock_policy = await get_stock_visibility_policy(db)
    ensure_not_stale(actual=product.updated_at, expected=payload.expected_updated_at)
    if payload.priority > 0 and not product.has_image:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Product needs an image before it can be prioritized")
    category_ids = set(payload.category_ids)
    if category_ids:
        valid_ids = set((await db.execute(select(ProductCategory.id).where(ProductCategory.id.in_(category_ids)))).scalars().all())
        if valid_ids != category_ids:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="One or more categories do not exist")
    before = serialize_admin_product(
        request,
        product,
        stock_policy=stock_policy,
    ).model_dump(mode="json")
    product.description = payload.description
    product.usage = payload.usage
    product.expiration = payload.expiration
    product.priority = payload.priority
    product.stock_reduction_override = payload.stock_reduction_override
    existing = {link.category_id: link for link in product.products_by_category}
    for category_id, link in existing.items():
        if category_id not in category_ids:
            await db.delete(link)
    for category_id in category_ids - set(existing):
        db.add(ProductByCategory(product_id=product.id, category_id=category_id))
    await db.flush()
    product = await _get_product(db, product.id)
    after = serialize_admin_product(request, product, stock_policy=stock_policy)
    await add_admin_audit(db, request, context, action="product.merchandise.update", entity_type="product", entity_id=product.id, before=before, after=after.model_dump(mode="json"))
    await db.commit()
    await _bump_catalog_cache()
    return after


@admin_catalog_router.post("/products/{product_id}/image", response_model=AdminProductRead)
async def upload_product_image(
    product_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("catalog.merchandise", write=True)),
) -> AdminProductRead:
    product = await _get_product(db, product_id)
    stock_policy = await get_stock_visibility_policy(db)
    target_path = product_image_path(product.id, product.system_id)
    if target_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Product does not have a source identifier",
        )
    before = serialize_admin_product(
        request,
        product,
        stock_policy=stock_policy,
    ).model_dump(mode="json")
    await save_product_image(target_path, await prepare_product_image(file))
    product.updated_at = ufa_now()
    await db.flush()
    result = serialize_admin_product(
        request,
        product,
        stock_policy=stock_policy,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="product.image.upload",
        entity_type="product",
        entity_id=product.id,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    await _bump_catalog_cache()
    return result


@admin_catalog_router.post(
    "/products/{product_id}/variants/{variant_id}/image",
    response_model=AdminProductRead,
)
async def upload_variant_image(
    product_id: int,
    variant_id: int,
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    context: AdminContext = Depends(require_permission("catalog.merchandise", write=True)),
) -> AdminProductRead:
    product = await _get_product(db, product_id)
    stock_policy = await get_stock_visibility_policy(db)
    variant = (
        await db.execute(
            select(Variant).where(
                Variant.id == variant_id,
                Variant.product_id == product_id,
            )
        )
    ).scalar_one_or_none()
    if variant is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Variant not found")
    target_path = variant_image_path(product.id, variant.system_id)
    if target_path is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Variant does not have a source identifier",
        )
    before = serialize_admin_product(
        request,
        product,
        stock_policy=stock_policy,
    ).model_dump(mode="json")
    await save_product_image(target_path, await prepare_product_image(file))
    product.updated_at = ufa_now()
    await db.flush()
    product = await _get_product(db, product.id)
    result = serialize_admin_product(
        request,
        product,
        stock_policy=stock_policy,
    )
    await add_admin_audit(
        db,
        request,
        context,
        action="product.variant_image.upload",
        entity_type="variant",
        entity_id=variant.id,
        before=before,
        after=result.model_dump(mode="json"),
    )
    await db.commit()
    await _bump_catalog_cache()
    return result


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
