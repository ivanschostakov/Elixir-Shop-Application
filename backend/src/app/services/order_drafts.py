from decimal import Decimal
from typing import Any

from fastapi import HTTPException, Request
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from starlette import status

from src.app.modules.users.me.schemas import CreateOrderDraftPayload, UpdateOrderDraftPayload
from src.database.crud import (
    create_delivery_address,
    create_delivery_recipient,
    get_delivery_address_by_fields,
    create_order_draft,
    delete_order_draft,
    get_delivery_address_by_id,
    get_delivery_addresses,
    get_delivery_recipient_by_fields,
    get_delivery_recipient_by_id,
    get_delivery_recipients,
    get_latest_order_draft_for_user,
    get_order_draft_by_id,
    get_order_drafts_for_user,
    update_order_draft,
)
from src.database.models import Basket, BasketItem, OrderDraft, OrderDraftItem, Product, User, Variant
from src.database.limits import (
    DELIVERY_ADDRESS_MAX_LENGTH,
    DELIVERY_CITY_MAX_LENGTH,
    DELIVERY_COMMENT_MAX_LENGTH,
    DELIVERY_LABEL_MAX_LENGTH,
    DELIVERY_POSTAL_CODE_MAX_LENGTH,
    EMAIL_MAX_LENGTH,
    EXTERNAL_ID_MAX_LENGTH,
    ORDER_DRAFT_COMMENT_MAX_LENGTH,
    ORDER_DRAFT_NAME_MAX_LENGTH,
    PERSON_NAME_MAX_LENGTH,
    WEBSITE_PHONE_MAX_LENGTH,
)
from src.database.schemas import (
    DeliveryAddressCreate,
    DeliveryAddressRead,
    DeliveryRecipientCreate,
    DeliveryRecipientRead,
    OrderDraftCheckoutOptionsRead,
    OrderDraftCreate,
    OrderDraftItemRead,
    OrderDraftRead,
    OrderDraftUpdate,
)
from src.product_media import build_products_media_url
from src.normalize import fit_text, optional_str


def _checkout_conflict(detail: str | dict[str, Any]) -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)


def _build_image_url(request: Request, *, product: Product | None, variant: Variant | None) -> str:
    if variant is not None and variant.image_path is not None:
        return build_products_media_url(str(request.base_url), variant.image_path)

    if product is not None and product.image_path is not None:
        return build_products_media_url(str(request.base_url), product.image_path)

    return build_products_media_url(str(request.base_url), None)


def _normalize_required_recipient_text(value: str | None, *, max_length: int, field_name: str) -> str:
    normalized = fit_text(optional_str(value), max_length)
    if normalized is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return normalized


def _normalize_recipient_contact(value: str | None, *, max_length: int) -> str:
    return fit_text(optional_str(value), max_length) or ""


def _normalize_order_draft_text(value: str | None, *, max_length: int) -> str | None:
    return fit_text(optional_str(value), max_length)


def _require_delivery_value(value, *, field_name: str):
    if value is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=f"{field_name} is required")
    return value


def _build_items_signature(items: list[BasketItem] | list[OrderDraftItem]) -> tuple[tuple[int, int], ...]:
    return tuple(sorted((item.variant_id, item.quantity) for item in items))


CREATE_ORDER_DRAFT_DELIVERY_FIELDS = (
    "mode",
    "provider",
    "country_code",
    "name",
    "full_address",
    "details",
    "city",
    "postal_code",
    "latitude",
    "longitude",
    "provider_reference",
    "delivery_calculation",
)
REQUIRED_CREATE_ORDER_DRAFT_DELIVERY_FIELDS = (
    "mode",
    "provider",
    "country_code",
    "name",
    "full_address",
    "latitude",
    "longitude",
    "delivery_calculation",
)


async def _find_duplicate_order_draft(
    session: AsyncSession,
    *,
    user_id: int,
    basket_items: list[BasketItem],
) -> OrderDraft | None:
    basket_signature = _build_items_signature(basket_items)
    if not basket_signature:
        return None

    existing_drafts = await get_order_drafts_for_user(session, user_id, limit=None)
    for existing_draft in existing_drafts:
        if _build_items_signature(existing_draft.items) == basket_signature:
            return existing_draft

    return None


async def _get_or_create_delivery_recipient(
    session: AsyncSession,
    *,
    data: DeliveryRecipientCreate,
):
    recipient = await get_delivery_recipient_by_fields(
        session,
        user_id=data.user_id,
        name=data.name,
        surname=data.surname,
        phone=data.phone,
        email=data.email,
    )
    if recipient is not None:
        return recipient

    return await create_delivery_recipient(session, data, commit=False)


async def _get_or_create_delivery_address(
    session: AsyncSession,
    *,
    data: DeliveryAddressCreate,
):
    address = await get_delivery_address_by_fields(
        session,
        user_id=data.user_id,
        mode=data.mode,
        provider=data.provider,
        country_code=data.country_code,
        full_address=data.full_address,
        details=data.details,
        city=data.city,
        postal_code=data.postal_code,
        provider_reference=data.provider_reference,
    )
    if address is not None:
        return address

    return await create_delivery_address(session, data, commit=False)


def _build_new_recipient_data(user_id: int, payload) -> DeliveryRecipientCreate:
    return DeliveryRecipientCreate(
        user_id=user_id,
        name=_normalize_required_recipient_text(payload.name, max_length=PERSON_NAME_MAX_LENGTH, field_name="Recipient name"),
        surname=_normalize_required_recipient_text(payload.surname, max_length=PERSON_NAME_MAX_LENGTH, field_name="Recipient surname"),
        phone=_normalize_recipient_contact(payload.phone, max_length=WEBSITE_PHONE_MAX_LENGTH),
        email=_normalize_recipient_contact(payload.email, max_length=EMAIL_MAX_LENGTH),
    )


def _build_create_delivery_address_data(user_id: int, payload: CreateOrderDraftPayload) -> DeliveryAddressCreate:
    full_address = fit_text(payload.full_address, DELIVERY_ADDRESS_MAX_LENGTH)
    if full_address is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Address is required")

    return DeliveryAddressCreate(
        user_id=user_id,
        mode=_require_delivery_value(payload.mode, field_name="Delivery mode"),
        provider=_require_delivery_value(payload.provider, field_name="Delivery provider"),
        country_code=_require_delivery_value(payload.country_code, field_name="Delivery country"),
        name=fit_text(payload.name or full_address, DELIVERY_LABEL_MAX_LENGTH) or full_address,
        full_address=full_address,
        details=fit_text(payload.details, DELIVERY_COMMENT_MAX_LENGTH),
        city=fit_text(payload.city, DELIVERY_CITY_MAX_LENGTH),
        postal_code=fit_text(payload.postal_code, DELIVERY_POSTAL_CODE_MAX_LENGTH),
        latitude=_require_delivery_value(payload.latitude, field_name="Delivery latitude"),
        longitude=_require_delivery_value(payload.longitude, field_name="Delivery longitude"),
        provider_reference=fit_text(payload.provider_reference, EXTERNAL_ID_MAX_LENGTH),
    )


def _build_new_delivery_address_data(draft: OrderDraft, payload) -> DeliveryAddressCreate:
    full_address = fit_text(payload.full_address, DELIVERY_ADDRESS_MAX_LENGTH)
    if full_address is None:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Address is required")

    template = draft.delivery_address
    mode = payload.mode if payload.mode is not None else template.mode if template is not None else None
    provider = payload.provider if payload.provider is not None else template.provider if template is not None else None
    country_code = payload.country_code if payload.country_code is not None else template.country_code if template is not None else None
    latitude = payload.latitude if payload.latitude is not None else template.latitude if template is not None else None
    longitude = payload.longitude if payload.longitude is not None else template.longitude if template is not None else None

    return DeliveryAddressCreate(
        user_id=draft.user_id,
        mode=_require_delivery_value(mode, field_name="Delivery mode"),
        provider=_require_delivery_value(provider, field_name="Delivery provider"),
        country_code=_require_delivery_value(country_code, field_name="Delivery country"),
        name=fit_text(payload.name or full_address, DELIVERY_LABEL_MAX_LENGTH) or full_address,
        full_address=full_address,
        details=fit_text(payload.details, DELIVERY_COMMENT_MAX_LENGTH) if "details" in payload.model_fields_set else (template.details if template is not None else None),
        city=fit_text(payload.city, DELIVERY_CITY_MAX_LENGTH) if "city" in payload.model_fields_set else (template.city if template is not None else None),
        postal_code=fit_text(payload.postal_code, DELIVERY_POSTAL_CODE_MAX_LENGTH) if "postal_code" in payload.model_fields_set else (template.postal_code if template is not None else None),
        latitude=_require_delivery_value(latitude, field_name="Delivery latitude"),
        longitude=_require_delivery_value(longitude, field_name="Delivery longitude"),
        provider_reference=fit_text(payload.provider_reference, EXTERNAL_ID_MAX_LENGTH) if "provider_reference" in payload.model_fields_set else (template.provider_reference if template is not None else None),
    )


async def _get_locked_basket(session: AsyncSession, user_id: int) -> Basket | None:
    stmt = select(Basket).where(Basket.user_id == user_id).with_for_update()
    return (await session.execute(stmt)).scalar_one_or_none()


async def _get_locked_basket_items(session: AsyncSession, basket_id: int) -> list[BasketItem]:
    stmt = (
        select(BasketItem)
        .options(selectinload(BasketItem.product), selectinload(BasketItem.variant))
        .where(BasketItem.basket_id == basket_id)
        .order_by(BasketItem.created_at.asc(), BasketItem.id.asc())
        .with_for_update()
    )
    return list((await session.execute(stmt)).scalars().all())


async def _get_locked_variants(session: AsyncSession, variant_ids: list[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}

    stmt = select(Variant).where(Variant.id.in_(variant_ids)).with_for_update()
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


async def _get_products_by_id(session: AsyncSession, product_ids: set[int]) -> dict[int, Product]:
    if not product_ids:
        return {}

    stmt = select(Product).where(Product.id.in_(product_ids))
    products = list((await session.execute(stmt)).scalars().all())
    return {product.id: product for product in products}


async def _get_variants_by_id(session: AsyncSession, variant_ids: set[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}

    stmt = (
        select(Variant)
        .options(selectinload(Variant.product))
        .where(Variant.id.in_(variant_ids))
    )
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


def _serialize_order_draft_item(
    request: Request,
    item: OrderDraftItem,
    *,
    products_by_id: dict[int, Product],
    variants_by_id: dict[int, Variant],
) -> OrderDraftItemRead:
    variant = variants_by_id.get(item.variant_id)
    product = products_by_id.get(item.product_id)
    if product is None and variant is not None:
        product = variant.product

    return OrderDraftItemRead(
        id=item.id,
        user_id=item.user_id,
        draft_id=item.draft_id,
        product_id=item.product_id,
        variant_id=item.variant_id,
        product_name=item.product_name,
        product_sku=item.product_sku,
        variant_name=item.variant_name,
        variant_sku=item.variant_sku,
        quantity=item.quantity,
        unit_price=item.unit_price,
        line_total=item.line_total,
        image_url=_build_image_url(request, product=product, variant=variant),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def serialize_order_drafts(request: Request, session: AsyncSession, drafts: list[OrderDraft]) -> list[OrderDraftRead]:
    if not drafts:
        return []

    product_ids = {
        item.product_id
        for draft in drafts
        for item in draft.items
    }
    variant_ids = {
        item.variant_id
        for draft in drafts
        for item in draft.items
    }
    products_by_id = await _get_products_by_id(session, product_ids)
    variants_by_id = await _get_variants_by_id(session, variant_ids)

    serialized_drafts: list[OrderDraftRead] = []
    for draft in drafts:
        serialized_drafts.append(
            OrderDraftRead(
                id=draft.id,
                user_id=draft.user_id,
                delivery_address_id=draft.delivery_address_id,
                recipient_id=draft.recipient_id,
                status=draft.status,
                items_count=draft.items_count,
                total_quantity=draft.total_quantity,
                basket_subtotal=draft.basket_subtotal,
                delivery_total=draft.delivery_total,
                grand_total=draft.grand_total,
                currency=draft.currency,
                delivery_period_min=draft.delivery_period_min,
                delivery_period_max=draft.delivery_period_max,
                draft_name=draft.draft_name,
                comment=draft.comment,
                delivery_address=DeliveryAddressRead.model_validate(draft.delivery_address) if draft.delivery_address is not None else None,
                recipient=DeliveryRecipientRead.model_validate(draft.recipient) if draft.recipient is not None else None,
                items=[
                    _serialize_order_draft_item(
                        request,
                        item,
                        products_by_id=products_by_id,
                        variants_by_id=variants_by_id,
                    )
                    for item in draft.items
                ],
                created_at=draft.created_at,
                updated_at=draft.updated_at,
            )
        )

    return serialized_drafts


async def serialize_order_draft(request: Request, session: AsyncSession, draft: OrderDraft) -> OrderDraftRead:
    serialized_drafts = await serialize_order_drafts(request, session, [draft])
    return serialized_drafts[0]


def _validate_checkout_items(items: list[BasketItem], variants_by_id: dict[int, Variant]) -> None:
    for item in items:
        variant = variants_by_id.get(item.variant_id)
        if variant is None:
            raise _checkout_conflict("Basket contains a variant that is no longer available")
        if variant.stock <= 0 or item.quantity > variant.stock:
            raise _checkout_conflict("Basket contains unavailable items")


def _build_draft_items_from_basket(
    *,
    user_id: int,
    draft_id: int,
    basket_items: list[BasketItem],
    variants_by_id: dict[int, Variant],
) -> tuple[list[OrderDraftItem], Decimal, int]:
    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    draft_items: list[OrderDraftItem] = []

    for basket_item in basket_items:
        variant = variants_by_id[basket_item.variant_id]
        unit_price = variant.price
        line_total = unit_price * basket_item.quantity
        basket_subtotal += line_total
        total_quantity += basket_item.quantity

        draft_items.append(
            OrderDraftItem(
                user_id=user_id,
                draft_id=draft_id,
                product_id=basket_item.product_id,
                variant_id=basket_item.variant_id,
                product_name=basket_item.product.name,
                product_sku=basket_item.product.sku,
                variant_name=variant.name,
                variant_sku=variant.sku,
                quantity=basket_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    return draft_items, basket_subtotal, total_quantity


async def _sync_order_draft_items_from_basket(
    session: AsyncSession,
    *,
    draft: OrderDraft,
    user_id: int,
    update_data: dict[str, Decimal | int | str | None],
) -> None:
    basket = await _get_locked_basket(session, user_id)
    basket_items = await _get_locked_basket_items(session, basket.id) if basket is not None else []

    delivery_total = update_data.get("delivery_total")
    if not isinstance(delivery_total, Decimal):
        delivery_total = draft.delivery_total

    if not basket_items:
        await session.execute(delete(OrderDraftItem).where(OrderDraftItem.draft_id == draft.id))
        if basket is not None:
            await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))

        update_data["items_count"] = 0
        update_data["total_quantity"] = 0
        update_data["basket_subtotal"] = Decimal("0.00")
        update_data["grand_total"] = delivery_total
        return

    variants_by_id = await _get_locked_variants(session, [item.variant_id for item in basket_items])
    _validate_checkout_items(basket_items, variants_by_id)
    draft_items, basket_subtotal, total_quantity = _build_draft_items_from_basket(
        user_id=user_id,
        draft_id=draft.id,
        basket_items=basket_items,
        variants_by_id=variants_by_id,
    )

    await session.execute(delete(OrderDraftItem).where(OrderDraftItem.draft_id == draft.id))
    session.add_all(draft_items)
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))

    update_data["items_count"] = len(draft_items)
    update_data["total_quantity"] = total_quantity
    update_data["basket_subtotal"] = basket_subtotal
    update_data["grand_total"] = basket_subtotal + delivery_total


async def create_order_draft_for_user(
    session: AsyncSession,
    *,
    user: User,
    payload: CreateOrderDraftPayload,
) -> OrderDraft:
    basket = await _get_locked_basket(session, user.id)
    if basket is None:
        raise _checkout_conflict("Basket is empty")

    basket_items = await _get_locked_basket_items(session, basket.id)
    if not basket_items:
        raise _checkout_conflict("Basket is empty")

    variants_by_id = await _get_locked_variants(session, [item.variant_id for item in basket_items])
    _validate_checkout_items(basket_items, variants_by_id)

    duplicate_draft = await _find_duplicate_order_draft(
        session,
        user_id=user.id,
        basket_items=basket_items,
    )
    if duplicate_draft is not None:
        raise _checkout_conflict({
            "message": "Черновик с такими товарами уже существует",
            "draft_id": duplicate_draft.id,
        })

    has_any_delivery_payload = any(field in payload.model_fields_set for field in CREATE_ORDER_DRAFT_DELIVERY_FIELDS)
    if has_any_delivery_payload:
        missing_delivery_fields = [
            field_name
            for field_name in REQUIRED_CREATE_ORDER_DRAFT_DELIVERY_FIELDS
            if getattr(payload, field_name) is None
        ]
        if missing_delivery_fields:
            raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Delivery data is incomplete")

    delivery_address = None
    if has_any_delivery_payload:
        delivery_address = await _get_or_create_delivery_address(
            session,
            data=_build_create_delivery_address_data(user.id, payload),
        )

    basket_subtotal = Decimal("0.00")
    total_quantity = 0
    draft_items: list[OrderDraftItem] = []

    for basket_item in basket_items:
        variant = variants_by_id[basket_item.variant_id]
        unit_price = variant.price
        line_total = unit_price * basket_item.quantity
        basket_subtotal += line_total
        total_quantity += basket_item.quantity

        draft_items.append(
            OrderDraftItem(
                user_id=user.id,
                draft_id=0,
                product_id=basket_item.product_id,
                variant_id=basket_item.variant_id,
                product_name=basket_item.product.name,
                product_sku=basket_item.product.sku,
                variant_name=variant.name,
                variant_sku=variant.sku,
                quantity=basket_item.quantity,
                unit_price=unit_price,
                line_total=line_total,
            )
        )

    delivery_total = payload.delivery_calculation.delivery_sum if payload.delivery_calculation is not None else Decimal("0.00")
    currency = payload.delivery_calculation.currency if payload.delivery_calculation is not None else "RUB"
    delivery_period_min = payload.delivery_calculation.period_min if payload.delivery_calculation is not None else None
    delivery_period_max = payload.delivery_calculation.period_max if payload.delivery_calculation is not None else None
    order_draft = await create_order_draft(
        session,
        OrderDraftCreate(
            user_id=user.id,
            delivery_address_id=delivery_address.id if delivery_address is not None else None,
            recipient_id=None,
            status="draft",
            items_count=len(draft_items),
            total_quantity=total_quantity,
            basket_subtotal=basket_subtotal,
            delivery_total=delivery_total,
            grand_total=basket_subtotal + delivery_total,
            currency=currency,
            delivery_period_min=delivery_period_min,
            delivery_period_max=delivery_period_max,
            draft_name=_normalize_order_draft_text(payload.draft_name, max_length=ORDER_DRAFT_NAME_MAX_LENGTH),
            comment=None,
        ),
        commit=False,
    )

    for draft_item in draft_items:
        draft_item.draft_id = order_draft.id

    session.add_all(draft_items)
    await session.flush()
    await session.execute(delete(BasketItem).where(BasketItem.basket_id == basket.id))
    await session.commit()

    created_draft = await get_order_draft_by_id(session, order_draft.id, user_id=user.id)
    if created_draft is None:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to load created order draft")

    return created_draft


async def get_order_draft_for_user(session: AsyncSession, *, user_id: int, draft_id: int) -> OrderDraft | None:
    return await get_order_draft_by_id(session, draft_id, user_id=user_id)


async def get_latest_order_draft_for_checkout(session: AsyncSession, *, user_id: int) -> OrderDraft | None:
    return await get_latest_order_draft_for_user(session, user_id)


async def get_recent_order_drafts_for_user(session: AsyncSession, *, user_id: int, limit: int = 10) -> list[OrderDraft]:
    return await get_order_drafts_for_user(session, user_id, limit=limit)


async def delete_order_draft_for_user(session: AsyncSession, *, user_id: int, draft_id: int) -> bool:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None:
        return False

    await delete_order_draft(session, draft)
    return True


async def get_order_draft_checkout_options_for_user(
    session: AsyncSession,
    *,
    user: User,
    draft_id: int,
    limit: int = 20,
) -> OrderDraftCheckoutOptionsRead | None:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user.id)
    if draft is None:
        return None

    addresses = await get_delivery_addresses(session, user_id=user.id, limit=limit)
    recipients = await get_delivery_recipients(session, user.id, limit=limit)
    if draft.recipient is not None and not any(recipient.id == draft.recipient.id for recipient in recipients):
        recipients.insert(0, draft.recipient)

    return OrderDraftCheckoutOptionsRead(
        addresses=[DeliveryAddressRead.model_validate(address) for address in addresses],
        recipients=[DeliveryRecipientRead.model_validate(recipient) for recipient in recipients],
    )


async def update_order_draft_for_user(
    session: AsyncSession,
    *,
    user_id: int,
    draft_id: int,
    payload: UpdateOrderDraftPayload,
) -> OrderDraft | None:
    draft = await get_order_draft_by_id(session, draft_id, user_id=user_id)
    if draft is None:
        return None

    if "recipient_id" in payload.model_fields_set and payload.new_recipient is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing recipient or create a new one")
    if payload.delivery_address_id is not None and payload.new_delivery_address is not None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Choose an existing address or create a new one")

    update_data: dict[str, Decimal | int | str | None] = {}
    if "draft_name" in payload.model_fields_set:
        update_data["draft_name"] = _normalize_order_draft_text(payload.draft_name, max_length=ORDER_DRAFT_NAME_MAX_LENGTH)
    if "comment" in payload.model_fields_set:
        update_data["comment"] = _normalize_order_draft_text(payload.comment, max_length=ORDER_DRAFT_COMMENT_MAX_LENGTH)
    if "recipient_id" in payload.model_fields_set:
        if payload.recipient_id is None:
            update_data["recipient_id"] = None
        else:
            recipient = await get_delivery_recipient_by_id(session, payload.recipient_id, user_id=user_id)
            if recipient is None:
                raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery recipient not found")
            update_data["recipient_id"] = recipient.id
    if payload.new_recipient is not None:
        created_recipient = await _get_or_create_delivery_recipient(
            session,
            data=_build_new_recipient_data(user_id, payload.new_recipient),
        )
        update_data["recipient_id"] = created_recipient.id
    if payload.delivery_address_id is not None:
        delivery_address = await get_delivery_address_by_id(session, payload.delivery_address_id)
        if delivery_address is None or delivery_address.user_id != user_id:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Delivery address not found")
        update_data["delivery_address_id"] = delivery_address.id
    if payload.new_delivery_address is not None:
        created_address = await _get_or_create_delivery_address(
            session,
            data=_build_new_delivery_address_data(draft, payload.new_delivery_address),
        )
        update_data["delivery_address_id"] = created_address.id
        if payload.new_delivery_address.delivery_calculation is not None:
            delivery_total = payload.new_delivery_address.delivery_calculation.delivery_sum
            update_data["delivery_total"] = delivery_total
            update_data["currency"] = payload.new_delivery_address.delivery_calculation.currency
            update_data["delivery_period_min"] = payload.new_delivery_address.delivery_calculation.period_min
            update_data["delivery_period_max"] = payload.new_delivery_address.delivery_calculation.period_max
            update_data["grand_total"] = draft.basket_subtotal + delivery_total
    if payload.sync_basket_items:
        await _sync_order_draft_items_from_basket(
            session,
            draft=draft,
            user_id=user_id,
            update_data=update_data,
        )

    update_payload = OrderDraftUpdate(**update_data)
    updated_draft = await update_order_draft(session, draft, update_payload)
    return await get_order_draft_by_id(session, updated_draft.id, user_id=user_id)
