from typing import Literal
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_admin_user, get_current_user
from src.app.services.review_attachments import (
    build_review_attachment_filename,
    save_review_attachment_file,
    validate_review_attachment,
    validate_review_attachments_count,
    validate_review_attachments_total_size,
    remove_review_attachment_file,
)
from src.database import get_db
from src.database.crud import (
    create_review_attachment,
    create_product_review,
    create_product,
    delete_product,
    get_review_by_id,
    has_user_purchased_product,
    get_product_by_id,
    get_product_review_stats,
    get_product_reviews,
    get_products,
    get_similar_products,
    update_product,
)
from src.database.models import User
from src.database.schemas import ProductCreate, ProductUpdate, ProductWithVariantsRead, ReviewCreate, ReviewEligibilityRead, ReviewRead

from .helpers import serialize_product_with_variants, serialize_products_with_variants, serialize_review, serialize_reviews

products_router = APIRouter(prefix="/products", tags=["products"])


@products_router.get("/{product_id}", response_model=ProductWithVariantsRead)
async def products_get_by_id(request: Request, product_id: int, db: AsyncSession = Depends(get_db)):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    review_stats = await get_product_review_stats(db, product_ids=[product.id])
    return serialize_product_with_variants(request, product, review_stats_by_product_id=review_stats)


@products_router.get("/{product_id}/similar", response_model=list[ProductWithVariantsRead])
async def products_get_similar(
    request: Request,
    product_id: int,
    limit: int = Query(default=6, ge=1, le=20),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    similar_products = await get_similar_products(db, product_id=product_id, offset=offset, limit=limit)
    review_stats = await get_product_review_stats(db, product_ids=[item.id for item in similar_products])
    return serialize_products_with_variants(
        request, similar_products, review_stats_by_product_id=review_stats,
    )


@products_router.get("/{product_id}/reviews", response_model=list[ReviewRead])
async def products_get_reviews(
    request: Request,
    product_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    reviews = await get_product_reviews(db, product_id=product_id, offset=offset, limit=limit)
    return serialize_reviews(request, reviews)


@products_router.get("/{product_id}/reviews/eligibility", response_model=ReviewEligibilityRead)
async def products_get_review_eligibility(
    product_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    can_review = await has_user_purchased_product(db, user_id=current_user.id, product_id=product_id)
    return ReviewEligibilityRead(can_review=can_review)


@products_router.post("/{product_id}/reviews", response_model=ReviewRead, status_code=status.HTTP_201_CREATED)
async def products_create_review(
    request: Request,
    product_id: int,
    value: int = Form(..., ge=0, le=5),
    text: str | None = Form(default=None),
    attachments: list[UploadFile] | None = File(default=None),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    product = await get_product_by_id(db, product_id)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    if not await has_user_purchased_product(db, user_id=current_user.id, product_id=product_id): raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only customers who bought this product can leave a review")

    data = ReviewCreate(value=value, text=text.strip() if text else None)
    uploaded_attachments = attachments or []
    validate_review_attachments_count(len(uploaded_attachments))

    created_file_paths: list[Path] = []
    total_size_bytes = 0

    try:
        review = await create_product_review(db, user_id=current_user.id, product_id=product_id, data=data, commit=False)
        for attachment in uploaded_attachments:
            content = await attachment.read()
            mime_type = validate_review_attachment(content, mime_type=attachment.content_type)
            total_size_bytes += len(content)
            validate_review_attachments_total_size(total_size_bytes)

            filename = build_review_attachment_filename(mime_type)
            await create_review_attachment(db, review_id=review.id, filename=filename, mime_type=mime_type, commit=False)
            saved_path = await save_review_attachment_file(review.id, filename=filename, content=content)
            created_file_paths.append(saved_path)

        await db.commit()
    
    except Exception:
        await db.rollback()
        for file_path in created_file_paths: remove_review_attachment_file(file_path)
        raise

    created_review = await get_review_by_id(db, review_id=review.id)
    if created_review is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created review")

    return serialize_review(request, created_review)


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
):
    products = await get_products(db, q=q, sku=sku, min_priority=min_priority, category_id=category_id, offset=offset, limit=limit, sort=sort)
    review_stats = await get_product_review_stats(db, product_ids=[product.id for product in products])
    return serialize_products_with_variants(request, products, review_stats_by_product_id=review_stats)


@products_router.post("", response_model=ProductWithVariantsRead, status_code=status.HTTP_201_CREATED)
async def products_create(request: Request, data: ProductCreate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)):
    try:
        product = await create_product(db, data)
        product = await get_product_by_id(db, product.id, include_out_of_stock=True)
        review_stats = await get_product_review_stats(db, product_ids=[product.id])
        return serialize_product_with_variants(request, product, review_stats_by_product_id=review_stats)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product with this sku or name already exists")


@products_router.patch("/{product_id}", response_model=ProductWithVariantsRead)
async def products_patch(request: Request, product_id: int, data: ProductUpdate, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)):
    product = await get_product_by_id(db, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    try:
        updated_product = await update_product(db, product, data)
        updated_product = await get_product_by_id(db, updated_product.id, include_out_of_stock=True)
        review_stats = await get_product_review_stats(db, product_ids=[updated_product.id])
        return serialize_product_with_variants(request, updated_product, review_stats_by_product_id=review_stats)

    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Product with this sku or name already exists")


@products_router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def products_delete(product_id: int, db: AsyncSession = Depends(get_db), _: User = Depends(get_current_admin_user)):
    product = await get_product_by_id(db, product_id, include_out_of_stock=True)
    if product is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")
    await delete_product(db, product)
