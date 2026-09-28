"""Read-only catalog boundary for the Telegram AI. No cart or customer tools."""
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from decimal import Decimal
from src.database.models import Product, ProductByCategory
from src.app.services.stock_visibility import get_stock_visibility_policy
from src.app.services.catalog_merchandising import apply_percent_discount, product_catalog_discount_percent
from src.app.services.ai.chat_tools import SHOP_AI_FUNCTION_TOOLS, ShopAIToolExecutor

CATALOG_NAMES = {"search_catalog_products", "get_catalog_product", "get_product_stock"}
CATALOG_TOOLS = [{**tool, "strict": False} for tool in SHOP_AI_FUNCTION_TOOLS if tool["name"] in CATALOG_NAMES]


class CatalogRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Literal["search_catalog_products", "get_catalog_product", "get_product_stock"]
    arguments: dict[str, Any] = Field(default_factory=dict)


def apply_visibility(result, products, policy):
    def variant(item):
        product = products.get(item["product_id"])
        item["stock"] = policy.visible_stock(item["stock"], product)
        item["in_stock"] = item["stock"] > 0
        item["original_price"] = item["price"]
        discount = product_catalog_discount_percent(product)
        item["catalog_discount_percent"] = str(discount)
        item["price"] = str(apply_percent_discount(Decimal(item["price"]), discount))
    for product in [*result.get("items", []), *([result["product"]] if result.get("product") else [])]:
        for item in product["variants"]:
            variant(item)
        product["in_stock"] = any(item["in_stock"] for item in product["variants"])
    for item in result.get("variants", []):
        variant(item)
    if result.get("variant"):
        variant(result["variant"])
    if "variants" in result:
        result["in_stock"] = any(item["in_stock"] for item in result["variants"])
    return result


async def read_catalog(db, payload: CatalogRequest):
    result = await ShopAIToolExecutor(db, user_id=0).execute(payload.name, payload.arguments)
    if not result.get("ok"):
        return {"ok": False, "error": result.get("error", "catalog_unavailable")}
    ids = {p["product_id"] for p in result.get("items", [])}
    if result.get("product"): ids.add(result["product"]["product_id"])
    if result.get("product_id"): ids.add(result["product_id"])
    if result.get("variant"): ids.add(result["variant"]["product_id"])
    products = {p.id: p for p in (await db.execute(select(Product).options(selectinload(Product.products_by_category).selectinload(ProductByCategory.category)).where(Product.id.in_(ids)))).scalars()} if ids else {}
    apply_visibility(result, products, await get_stock_visibility_policy(db))
    return {**result, "source": "mobile_app_catalog", "currency": "RUB",
            "price_note": "Публичная цена приложения с каталожной скидкой, без персональной скидки; итоговую цену и наличие проверяйте в месте покупки. Ассортимент WebApp может отличаться."}
