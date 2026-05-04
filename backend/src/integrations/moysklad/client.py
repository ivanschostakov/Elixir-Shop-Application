from decimal import Decimal
from typing import Any
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import delete

from src.database.crud import create_product, create_variant
from src.database.schemas import ProductCreate, VariantCreate
from src.database.models import Product, Variant
from config import MOY_SKLAD_TOKEN, MOY_SKLAD_BASE_URL


class AsyncMoyskladClient:
    def __init__(self, token: str = MOY_SKLAD_TOKEN, base_url: str = MOY_SKLAD_BASE_URL, timeout: float = 30.0):
        self._client = AsyncClient(base_url=base_url, timeout=timeout, headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/json;charset=utf-8",
            "Content-Type": "application/json;charset=utf-8",
        })

    async def close(self) -> None: await self._client.aclose()

    def _money(self, value: float | int | None) -> Decimal:
        if value is None: return Decimal("0")
        return Decimal(str(value)) / Decimal("100")

    def _sale_price(self, item: dict[str, Any]) -> Decimal:
        return self._money(item.get("salePrices", [{}])[0].get("value"))

    async def _get_products_page(self, limit: int = 100, offset: int = 0, **params: Any) -> dict[str, Any]:
        params["limit"] = limit
        params["offset"] = offset
        params["filter"] = "pathName!=Товары интернет-магазинов/elixirpeptide.ru"

        response = await self._client.get("/entity/product", params=params)
        response.raise_for_status()
        return response.json()

    async def get_products(self, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            data = await self._get_products_page(limit=100, offset=offset, **params)
            batch = data.get("rows", [])
            rows.extend(batch)
            if len(batch) < 100: break
            offset += 100

        return rows

    async def _get_variants_page(self, limit: int = 100, offset: int = 0, expand: str | None = "product", **params: Any) -> dict[str, Any]:
        params["limit"] = limit
        params["offset"] = offset
        if expand is not None: params["expand"] = expand

        response = await self._client.get("/entity/variant", params=params)
        response.raise_for_status()
        return response.json()

    async def get_moysklad_variants(self, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            data = await self._get_variants_page(limit=100, offset=offset, **params)
            batch = data.get("rows", [])
            rows.extend(batch)
            if len(batch) < 100: break
            offset += 100

        return rows

    async def _get_stocks_page(self, limit: int = 100, offset: int = 0, **params: Any) -> dict[str, Any]:
        params["limit"] = limit
        params["offset"] = offset
        params["filter"] = "pathName!=Товары интернет-магазинов/elixirpeptide.ru"

        response = await self._client.get("/report/stock/all", params=params)
        response.raise_for_status()
        return response.json()

    async def get_stocks_report(self, **params: Any) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        offset = 0

        while True:
            data = await self._get_stocks_page(limit=100, offset=offset, **params)
            batch = data.get("rows", [])
            rows.extend(batch)
            if len(batch) < 100: break
            offset += 100

        return rows

    async def initial_sync(self, session: AsyncSession) -> None:
        products = await self.get_products()
        variants = await self.get_moysklad_variants()
        stocks = await self.get_stocks_report()

        await session.execute(delete(Variant))
        await session.execute(delete(Product))
        await session.flush()

        products_by_external_code = {
            product["externalCode"]: product
            for product in products
            if product.get("externalCode")
        }

        stocks_by_external_code = {
            stock["externalCode"]: stock
            for stock in stocks
            if stock.get("externalCode")
        }

        variants_by_product_external_code: dict[str, list[dict[str, Any]]] = {}

        for variant in variants:
            external_code = variant.get("externalCode")
            if not external_code: continue
            if external_code not in products_by_external_code: continue

            variants_by_product_external_code.setdefault(external_code, []).append(variant)

        for external_code, moy_product in products_by_external_code.items():
            product = await create_product(session, ProductCreate(
                system_id=moy_product["id"],
                sku=moy_product.get("article") or moy_product.get("code"),
                name=moy_product["name"],
                priority=0,
            ))

            for moy_variant in variants_by_product_external_code.get(external_code, []):
                stock = stocks_by_external_code.get(moy_variant.get("externalCode"))

                await create_variant(session, VariantCreate(
                    system_id=moy_variant["id"],
                    product_id=product.id,
                    sku=moy_variant.get("code"),
                    name=moy_variant["name"],
                    stock=int(stock.get("quantity", 0)) if stock else 0,
                    price=self._sale_price(moy_variant),
                ))

        await session.commit()

moysklad_client = AsyncMoyskladClient()
