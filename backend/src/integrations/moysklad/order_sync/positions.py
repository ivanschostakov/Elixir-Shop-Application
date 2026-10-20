from decimal import Decimal
from typing import Any
from uuid import UUID
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import Order, Product, Variant
from src.integrations.moysklad.client import MoySkladClient, moysklad_money
from src.integrations.moysklad.rows import synthetic_variant_id
from src.integrations.moysklad.settlement_checkout import order_settlement, money as settlement_money


async def _load_assortment_refs(session: AsyncSession, *, variant_ids: list[int]) -> dict[int, tuple[str, UUID]]:
    if not variant_ids: return {}
    stmt = select(Variant.id, Variant.system_id, Product.system_id) .join(Product, Product.id == Variant.product_id) .where(Variant.id.in_(variant_ids))

    rows = (await session.execute(stmt)).all()
    refs: dict[int, tuple[str, UUID]] = {}
    for variant_id, variant_system_id, product_system_id in rows:
        if variant_system_id is not None and product_system_id is not None and variant_system_id == synthetic_variant_id(product_system_id):
            refs[int(variant_id)] = ("product", product_system_id)
            continue
        if variant_system_id is not None:
            refs[int(variant_id)] = ("variant", variant_system_id)
            continue

        if product_system_id is not None: refs[int(variant_id)] = ("product", product_system_id)
    return refs


def _build_customerorder_positions(*, moysklad_client: MoySkladClient, assortment_refs: dict[int, tuple[str, UUID]], order: Order) -> tuple[list[dict[str, Any]], list[int]]:
    positions: list[dict[str, Any]] = []
    missing_variant_ids = [int(item.variant_id) for item in order.items if int(item.variant_id) not in assortment_refs]
    if missing_variant_ids: return positions, missing_variant_ids
    line_amounts = [moysklad_money(Decimal(item.line_total)) for item in order.items]
    subtotal = sum(line_amounts)
    settlement = order_settlement(order)
    gross = settlement_money(settlement["gross_rubles"]) if settlement else Decimal(order.grand_total)
    target = moysklad_money(gross - Decimal(order.delivery_total))
    if subtotal != moysklad_money(Decimal(order.basket_subtotal)) or not 0 <= target <= subtotal: raise ValueError("Order totals are inconsistent; MoySklad sync requires manual review")
    if not subtotal: allocated = [0] * len(line_amounts)
    else:
        # Allocate whole kopecks, then distribute the rounding remainder deterministically.
        allocated = [amount * target // subtotal for amount in line_amounts]
        remainder_order = sorted(range(len(line_amounts)), key=lambda i: (line_amounts[i] * target % subtotal, -i), reverse=True)
        for index in remainder_order[:target - sum(allocated)]: allocated[index] += 1

    for item, line_total in zip(order.items, allocated):
        quantity = int(item.quantity)
        if quantity <= 0 or quantity != item.quantity: raise ValueError("Invalid order item quantity")
        assortment_ref = assortment_refs[int(item.variant_id)]
        entity_type, entity_id = assortment_ref
        unit_minor, extra_units = divmod(line_total, quantity)
        for count, price in [(quantity - extra_units, unit_minor), (extra_units, unit_minor + 1)]:
            if not count: continue
            positions.append(moysklad_client.build_customerorder_position(assortment_entity_type=entity_type, assortment_id=entity_id, quantity=count, unit_price=Decimal(price) / 100, discount=Decimal("0.00"),))
    return positions, missing_variant_ids
