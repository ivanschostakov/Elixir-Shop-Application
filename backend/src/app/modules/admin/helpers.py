from decimal import Decimal

from fastapi import HTTPException, Request
from starlette import status

from src.app.modules.admin.schemas import (
    AdminBannerRead,
    AdminCategoryRead,
    AdminOrderDetail,
    AdminOrderItemRead,
    AdminOrderListItem,
    AdminProductRead,
    AdminReviewRead,
    AdminVariantRead,
    CustomerCompact,
)
from src.app.modules.products.helpers import review_attachment_path
from src.app.services.review_attachments import build_review_attachment_url
from src.database.models import Banner, Order, Product, ProductCategory, Review
from src.database.models.orders.history import get_order_status_code
from src.product_media import build_products_media_url


def ensure_not_stale(*, actual, expected) -> None:
    if actual != expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "stale_record", "message": "Record was changed by another administrator"},
        )


def customer_compact(user) -> CustomerCompact:
    return CustomerCompact(
        id=user.id,
        name=user.name,
        surname=user.surname,
        email=user.email,
        phone_number=user.phone_number,
    )


def serialize_admin_order(order: Order) -> AdminOrderListItem:
    return AdminOrderListItem(
        id=order.id,
        order_code=order.order_code,
        status=order.status,
        status_code=get_order_status_code(order),
        customer=customer_compact(order.user),
        items_count=order.items_count,
        total_quantity=order.total_quantity,
        grand_total=order.grand_total,
        currency=order.currency,
        payment_method=order.payment_method,
        payment_status=order.payment_status,
        delivery_service=order.selected_delivery_service,
        is_paid=order.is_paid,
        is_canceled=order.is_canceled,
        amocrm_lead_id=order.amocrm_lead_id,
        created_at=order.created_at,
        updated_at=order.updated_at,
    )


def serialize_admin_order_detail(order: Order) -> AdminOrderDetail:
    base = serialize_admin_order(order).model_dump()
    recipient = order.recipient
    address = order.delivery_address
    benefits = (order.checkout_snapshot or {}).get("benefits") or {}
    return AdminOrderDetail(
        **base,
        basket_subtotal=order.basket_subtotal,
        delivery_total=order.delivery_total,
        comment=order.comment,
        delivery_string=order.delivery_string,
        delivery_period_min=order.delivery_period_min,
        delivery_period_max=order.delivery_period_max,
        payment_provider=order.payment_provider,
        payment_invoice_id=order.payment_invoice_id,
        payment_paid_at=order.payment_paid_at,
        payment_error=order.payment_error,
        delivery_created_at=order.delivery_created_at,
        delivery_provider_ref=order.delivery_provider_ref,
        yandex_request_id=order.yandex_request_id,
        moysklad_customerorder_id=str(order.moysklad_customerorder_id) if order.moysklad_customerorder_id else None,
        moysklad_invoiceout_id=str(order.moysklad_invoiceout_id) if order.moysklad_invoiceout_id else None,
        recipient={
            "name": recipient.name,
            "surname": recipient.surname,
            "phone": recipient.phone,
            "email": recipient.email,
        } if recipient else {},
        address={
            "name": address.name,
            "full_address": address.full_address,
            "details": address.details,
            "city": address.city,
            "postal_code": address.postal_code,
            "country_code": address.country_code,
            "provider": address.provider,
        } if address else {},
        items=[AdminOrderItemRead(
            id=item.id,
            product_id=item.product_id,
            variant_id=item.variant_id,
            product_name=item.product_name,
            product_sku=item.product_sku,
            variant_name=item.variant_name,
            variant_sku=item.variant_sku,
            quantity=item.quantity,
            unit_price=item.unit_price,
            line_total=item.line_total,
        ) for item in order.items],
        benefits=benefits if isinstance(benefits, dict) else {},
    )


def serialize_admin_product(request: Request, product: Product) -> AdminProductRead:
    return AdminProductRead(
        id=product.id,
        system_id=str(product.system_id),
        sku=product.sku,
        name=product.name,
        description=product.description,
        usage=product.usage,
        expiration=product.expiration,
        in_stock=product.in_stock,
        archived=product.archived,
        priority=product.priority,
        image_url=build_products_media_url(str(request.base_url), product.image_path),
        category_ids=sorted(link.category_id for link in product.products_by_category),
        variants=[AdminVariantRead(
            id=variant.id,
            system_id=str(variant.system_id),
            sku=variant.sku,
            name=variant.name,
            stock=variant.stock,
            price=variant.price,
            archived=variant.archived,
        ) for variant in product.variants],
        updated_at=product.updated_at,
    )


def serialize_admin_review(request: Request, review: Review, *, product_name: str) -> AdminReviewRead:
    if review.rejected_at is not None:
        review_status = "rejected"
    elif review.moderated:
        review_status = "published"
    else:
        review_status = "pending"
    if review.user is not None:
        author_name = " ".join(part for part in (review.user.name, review.user.surname) if part).strip()
        author_email = review.user.email
    else:
        author_name = review.guest_name or "Гость"
        author_email = review.guest_email
    return AdminReviewRead(
        id=review.id,
        product_id=review.product_id,
        product_name=product_name,
        user_id=review.user_id,
        author_name=author_name,
        author_email=author_email,
        value=review.value,
        text=review.text,
        answer=review.answer,
        status=review_status,
        attachments=[build_review_attachment_url(request, review_attachment_path(attachment.review_id, attachment.filename)) for attachment in review.attachments],
        created_at=review.created_at,
        updated_at=review.updated_at,
    )


def serialize_category(category: ProductCategory) -> AdminCategoryRead:
    return AdminCategoryRead(
        id=category.id,
        name=category.name,
        description=category.description,
        archived=category.archived,
        created_at=category.created_at,
        updated_at=category.updated_at,
    )


def serialize_banner(banner: Banner) -> AdminBannerRead:
    return AdminBannerRead(
        id=banner.id,
        image_path=banner.image_path,
        inner_link=banner.inner_link,
        outer_link=banner.outer_link,
        priority=banner.priority,
        archived=banner.archived,
        created_at=banner.created_at,
        updated_at=banner.updated_at,
    )
