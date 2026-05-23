from decimal import Decimal
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import MOY_SKLAD_ORDER_SYNC_ENABLED, MOY_SKLAD_ORGANIZATION_ID
from src.database.models import Order, Product, User, Variant
from src.normalize import coerce_uuid, optional_str

from .client import MoySkladClient, get_moysklad_client
from .idempotency import (
    build_counterparty_external_code,
    build_customerorder_external_code,
    build_sync_id,
)
from .schemas import MoySkladOrderSyncResult

log = logging.getLogger(__name__)


def _full_name(user: User, order: Order) -> str:
    recipient = order.recipient
    parts = [
        optional_str(recipient.name) if recipient is not None else None,
        optional_str(recipient.surname) if recipient is not None else None,
    ]
    full_name = " ".join(part for part in parts if part)
    if full_name: return full_name

    fallback_parts = [optional_str(user.name), optional_str(user.surname)]
    fallback_name = " ".join(part for part in fallback_parts if part)
    if fallback_name: return fallback_name

    email_fallback = optional_str(user.email)
    return email_fallback or f"User {user.id}"


def _counterparty_email(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_email = optional_str(recipient.email)
        if recipient_email: return recipient_email

    return optional_str(user.email)


def _counterparty_phone(user: User, order: Order) -> str | None:
    recipient = order.recipient
    if recipient is not None:
        recipient_phone = optional_str(recipient.phone)
        if recipient_phone: return recipient_phone

    return optional_str(user.phone_number)


def _counterparty_address(order: Order) -> str | None:
    if order.delivery_address is not None:
        address = optional_str(order.delivery_address.full_address)
        if address: return address

    return optional_str(order.delivery_string)


def _configured_organization_id() -> UUID | None:
    configured_id = coerce_uuid(MOY_SKLAD_ORGANIZATION_ID)
    if configured_id is None and optional_str(MOY_SKLAD_ORGANIZATION_ID): log.warning("MOY_SKLAD_ORGANIZATION_ID is not a valid UUID: %s", MOY_SKLAD_ORGANIZATION_ID)
    return configured_id


async def _load_assortment_refs(session: AsyncSession, *, variant_ids: list[int]) -> dict[int, tuple[str, UUID]]:
    if not variant_ids: return {}
    stmt = select(Variant.id, Variant.system_id, Product.system_id) .join(Product, Product.id == Variant.product_id) .where(Variant.id.in_(variant_ids))

    rows = (await session.execute(stmt)).all()
    refs: dict[int, tuple[str, UUID]] = {}
    for variant_id, variant_system_id, product_system_id in rows:
        if variant_system_id is not None:
            refs[int(variant_id)] = ("variant", variant_system_id)
            continue

        if product_system_id is not None: refs[int(variant_id)] = ("product", product_system_id)
    return refs


def _build_customerorder_positions(*, moysklad_client: MoySkladClient, assortment_refs: dict[int, tuple[str, UUID]], order: Order) -> tuple[list[dict[str, Any]], list[int]]:
    positions: list[dict[str, Any]] = []
    missing_variant_ids: list[int] = []

    for item in order.items:
        assortment_ref = assortment_refs.get(int(item.variant_id))
        if assortment_ref is None:
            missing_variant_ids.append(int(item.variant_id))
            continue

        entity_type, entity_id = assortment_ref
        positions.append(moysklad_client.build_customerorder_position(
            assortment_entity_type=entity_type,
            assortment_id=entity_id,
            quantity=item.quantity,
            unit_price=Decimal(item.unit_price),
        ))

    return positions, missing_variant_ids


def _build_order_description(order: Order) -> str:
    comment = optional_str(order.comment)
    if comment: return f"{order.order_code}. {comment}"
    return order.order_code


async def sync_order_to_moysklad(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    if not MOY_SKLAD_ORDER_SYNC_ENABLED: return MoySkladOrderSyncResult(enabled=False, skipped_reason="disabled")

    moysklad_client = get_moysklad_client()
    if not moysklad_client.is_configured(): return MoySkladOrderSyncResult(enabled=True, skipped_reason="client_not_configured")
    if not order.items: return MoySkladOrderSyncResult(enabled=True, skipped_reason="empty_order")

    organization_id = _configured_organization_id()
    if organization_id is None: return MoySkladOrderSyncResult(enabled=True, skipped_reason="organization_not_configured")

    counterparty_external_code = build_counterparty_external_code(user_id=user.id)
    counterparty_sync_id = build_sync_id(scope="counterparty", key=counterparty_external_code)
    counterparty_result = await moysklad_client.resolve_or_sync_counterparty(
        existing_counterparty_id=user.moysklad_counterparty_id,
        external_code=counterparty_external_code,
        sync_id=counterparty_sync_id,
        name=_full_name(user, order),
        email=_counterparty_email(user, order),
        phone=_counterparty_phone(user, order),
        actual_address=_counterparty_address(order),
    )

    if user.moysklad_counterparty_id != counterparty_result.counterparty_id:
        user.moysklad_counterparty_id = counterparty_result.counterparty_id
        await session.flush()
        await session.commit()

    variant_ids = [int(item.variant_id) for item in order.items]
    assortment_refs = await _load_assortment_refs(session, variant_ids=variant_ids)
    positions, missing_variant_ids = _build_customerorder_positions(
        moysklad_client=moysklad_client,
        assortment_refs=assortment_refs,
        order=order,
    )

    if missing_variant_ids:
        unique_missing = sorted(set(missing_variant_ids))
        log.warning("Skipping MoySklad order sync because assortment refs are missing for variants=%s order_id=%s", unique_missing, order.id)
        return MoySkladOrderSyncResult(
            enabled=True,
            skipped_reason="missing_assortment_refs",
            counterparty=counterparty_result,
        )

    if not positions: return MoySkladOrderSyncResult(
        enabled=True,
        skipped_reason="empty_positions",
        counterparty=counterparty_result,
    )

    customerorder_external_code = build_customerorder_external_code(order_id=order.id)
    customerorder_sync_id = build_sync_id(scope="customerorder", key=customerorder_external_code)
    customerorder_result = await moysklad_client.resolve_or_sync_customerorder(
        existing_customerorder_id=order.moysklad_customerorder_id,
        external_code=customerorder_external_code,
        sync_id=customerorder_sync_id,
        organization_id=organization_id,
        counterparty_id=counterparty_result.counterparty_id,
        positions=positions,
        moment=order.created_at,
        description=_build_order_description(order),
    )

    if order.moysklad_customerorder_id != customerorder_result.customerorder_id:
        order.moysklad_customerorder_id = customerorder_result.customerorder_id
        await session.flush()
        await session.commit()

    return MoySkladOrderSyncResult(
        enabled=True,
        counterparty=counterparty_result,
        customerorder=customerorder_result,
    )


async def sync_order_to_moysklad_safe(session: AsyncSession, *, order: Order, user: User) -> MoySkladOrderSyncResult:
    try: return await sync_order_to_moysklad(session, order=order, user=user)
    except Exception:
        await session.rollback()
        log.exception("MoySklad order sync failed order_id=%s user_id=%s", order.id, user.id)
        return MoySkladOrderSyncResult(enabled=MOY_SKLAD_ORDER_SYNC_ENABLED, skipped_reason="sync_error")
