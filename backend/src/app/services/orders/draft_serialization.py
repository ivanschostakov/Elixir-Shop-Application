from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import OrderDraft, OrderDraftItem, Product, Variant
from src.database.schemas import DeliveryAddressRead, DeliveryRecipientRead, OrderDraftItemRead, OrderDraftRead
from .serialization_utils import build_order_item_image_url, get_products_by_id, get_variants_by_id


def _serialize_order_draft_item(request: Request, item: OrderDraftItem, *, products_by_id: dict[int, Product], variants_by_id: dict[int, Variant]) -> OrderDraftItemRead:
    variant = variants_by_id.get(item.variant_id)
    product = products_by_id.get(item.product_id)
    if product is None and variant is not None: product = variant.product
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
        image_url=build_order_item_image_url(request, product=product, variant=variant),
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


async def serialize_order_drafts(request: Request, session: AsyncSession, drafts: list[OrderDraft]) -> list[OrderDraftRead]:
    if not drafts: return []

    product_ids = {item.product_id for draft in drafts for item in draft.items}
    variant_ids = {item.variant_id for draft in drafts for item in draft.items}
    products_by_id = await get_products_by_id(session, product_ids)
    variants_by_id = await get_variants_by_id(session, variant_ids)

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
                    _serialize_order_draft_item(request, item, products_by_id=products_by_id, variants_by_id=variants_by_id)
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
