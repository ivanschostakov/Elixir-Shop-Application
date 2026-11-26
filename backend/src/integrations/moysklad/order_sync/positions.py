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
    benefits = (order.checkout_snapshot or {}).get("benefits") or {}
    welcome = sum(moysklad_money(Decimal(row["discount_amount"])) for row in benefits.get("applications", [])
                  if row.get("source_kind") == "app_welcome")
    target += welcome  # First reconstruct the goods after ordinary discounts.
    if target > subtotal:
        raise ValueError("Welcome discount does not match the goods total")
    priced_items = benefits.get("priced_items") or []
    if priced_items:
        priced_by_id = {row["variant_id"]: row for row in priced_items}
        if len(priced_by_id) != len(order.items) or any(
            item.variant_id not in priced_by_id or priced_by_id[item.variant_id]["quantity"] != item.quantity
            for item in order.items):
            raise ValueError("Priced order items do not match the exported order")
        allocated = [moysklad_money(Decimal(priced_by_id[item.variant_id]["line_total"])) for item in order.items]
        if sum(allocated) != target:
            raise ValueError("Priced item amounts do not match the order total")
    elif not subtotal: allocated = [0] * len(line_amounts)
    else:
        excluded = set(benefits.get("discount_excluded_product_ids") or [])
        fixed = [amount if getattr(item, "product_id", None) in excluded else 0 for item, amount in zip(order.items, line_amounts)]
        weights = [amount if not fixed_amount else 0 for amount, fixed_amount in zip(line_amounts, fixed)]
        eligible_subtotal = sum(weights)
        eligible_target = target - sum(fixed)
        if eligible_target < 0 or (eligible_target and not eligible_subtotal):
            raise ValueError("Discount affects excluded products")
        # Allocate whole kopecks, then distribute the rounding remainder deterministically.
        allocated = [amount * eligible_target // eligible_subtotal if eligible_subtotal else 0 for amount in weights]
        remainder_order = sorted(range(len(weights)), key=lambda i: (weights[i] * eligible_target % eligible_subtotal, -i), reverse=True) if eligible_subtotal else []
        for index in remainder_order[:eligible_target - sum(allocated)]: allocated[index] += 1
        allocated = [amount + fixed_amount for amount, fixed_amount in zip(allocated, fixed)]

    if welcome:
        if welcome * 2 > target or sum(allocated) != target:
            raise ValueError("Welcome discount exceeds the goods limit")
        payable = target - welcome
        rounded = [line * payable // target for line in allocated]
        by_remainder = sorted(range(len(allocated)), key=lambda i: -(allocated[i] * payable % target))
        for i in by_remainder[:payable - sum(rounded)]:
            rounded[i] += 1
        allocated = rounded

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
