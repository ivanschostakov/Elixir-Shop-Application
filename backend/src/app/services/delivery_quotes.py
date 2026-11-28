from __future__ import annotations

import logging
from typing import Any, Iterable

import httpx
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models import Product, User, Variant
from src.integrations.bitrix_delivery import BitrixDeliveryClient, BitrixDeliveryError
from src.integrations.delivery.cdek import get_cdek_client
from src.integrations.delivery.cdek.client import AsyncCDEKClient


logger = logging.getLogger(__name__)


def _address_value(address: Any, name: str) -> Any:
    if isinstance(address, dict):
        return address.get(name)
    return getattr(address, name, None)


async def _lookup_fias_guid(cdek: AsyncCDEKClient, city_code: int) -> str | None:
    try:
        return await cdek.city_fias_guid(city_code)
    except (httpx.HTTPError, HTTPException, ValueError) as exc:
        logger.warning("CDEK FIAS lookup unavailable city_code=%s error=%s", city_code, type(exc).__name__)
        raise HTTPException(
            status_code=502,
            detail="Сервис СДЭК временно недоступен. Повторите расчёт доставки позже.",
        ) from exc


async def build_bitrix_delivery_items(
    session: AsyncSession,
    items: Iterable[Any],
) -> list[dict[str, Any]]:
    normalized = [
        (int(_address_value(item, "variant_id") or 0), int(_address_value(item, "quantity") or 0))
        for item in items
    ]
    if not normalized or any(variant_id <= 0 or quantity <= 0 for variant_id, quantity in normalized):
        raise HTTPException(status_code=409, detail="Корзина пуста или содержит некорректные товары.")

    variant_ids = {variant_id for variant_id, _quantity in normalized}
    stmt = (
        select(Variant)
        .options(selectinload(Variant.product))
        .where(Variant.id.in_(variant_ids))
    )
    variants = list((await session.execute(stmt)).scalars().all())
    variants_by_id = {variant.id: variant for variant in variants}
    if len(variants_by_id) != len(variant_ids):
        raise HTTPException(status_code=409, detail="Часть товаров корзины больше недоступна.")

    return [
        {
            "variant_system_id": str(variants_by_id[variant_id].system_id),
            "product_system_id": str(variants_by_id[variant_id].product.system_id),
            "quantity": quantity,
        }
        for variant_id, quantity in normalized
    ]


async def calculate_authoritative_cdek_quote(
    session: AsyncSession,
    *,
    user: User,
    address: Any,
    items: Iterable[Any],
    cdek: AsyncCDEKClient | None = None,
) -> dict[str, Any]:
    provider = str(_address_value(address, "provider") or "").upper()
    if provider != "CDEK":
        raise ValueError("Authoritative Bitrix quote is only available for CDEK")

    latitude = _address_value(address, "latitude")
    longitude = _address_value(address, "longitude")
    if latitude is None or longitude is None:
        raise HTTPException(status_code=422, detail="Для расчёта доставки не хватает координат адреса.")

    cdek_client = cdek or get_cdek_client()
    mode = str(_address_value(address, "mode") or "").lower()
    delivery_point_code = str(_address_value(address, "provider_reference") or "").strip()
    if mode in {"pickup", "office"} and delivery_point_code:
        city_code = await cdek_client.get_delivery_point_city_code(
            delivery_point_code,
            country_code=_address_value(address, "country_code"),
        )
    else:
        city_code = await cdek_client.resolve_city_code(
            latitude=float(latitude),
            longitude=float(longitude),
            city=_address_value(address, "city"),
            postal_code=_address_value(address, "postal_code"),
            country_code=_address_value(address, "country_code"),
        )
    bitrix_items = await build_bitrix_delivery_items(session, items)
    destination = {
        "cdek_city_code": city_code,
        "country_code": _address_value(address, "country_code"),
        "postal_code": _address_value(address, "postal_code"),
        "address": _address_value(address, "full_address"),
        "city": _address_value(address, "city"),
        "latitude": float(latitude),
        "longitude": float(longitude),
    }
    bitrix = BitrixDeliveryClient()

    async def quote(target: dict[str, Any]) -> dict[str, Any]:
        return await bitrix.quote(mode=mode, destination=target, items=bitrix_items, user_email=user.email)

    try:
        try:
            return await quote(destination)
        except BitrixDeliveryError as original:
            if original.code != "destination_not_found" or destination["country_code"] != "RU":
                raise
            guid = await _lookup_fias_guid(cdek_client, city_code)
            if not guid:
                raise
            return await quote({**destination, "fias_guid": guid})
    except BitrixDeliveryError as exception:
        logger.warning(
            "Authoritative Bitrix delivery quote failed code=%s status=%s cdek_city_code=%s mode=%s",
            exception.code,
            exception.status_code,
            city_code,
            mode,
        )
        if exception.code in {"destination_not_found", "calculation_failed"}:
            raise HTTPException(status_code=exception.status_code, detail=(
                "Для этого адреса СДЭК не подтвердил стоимость доставки. Выберите другой пункт выдачи "
                "или способ доставки."
            )) from exception
        raise HTTPException(status_code=exception.status_code, detail=exception.message_ru) from exception
