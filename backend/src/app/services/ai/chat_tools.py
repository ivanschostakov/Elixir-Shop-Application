import json
import time

from decimal import Decimal
from typing import Any
from sqlalchemy import desc, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database.models.basket.basket import Basket
from src.database.models.basket.basket_item import BasketItem
from src.database.models.catalog.product import Product
from src.database.models.catalog.variant import Variant
from src.database.models.orders.draft import OrderDraft
from src.database.models.orders.order import Order
from .schemas import ShopAIFunctionTool, ToolArguments, ToolMethod, ShopAIToolCall

SHOP_AI_FUNCTION_TOOLS: list[ShopAIFunctionTool] = [
    {
        "type": "function",
        "name": "search_catalog_products",
        "description": "Search or browse the app catalog by product name, sku, or description. If query is empty, returns a catalog slice.",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "maxLength": 200},
                "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                "offset": {"type": "integer", "minimum": 0, "maximum": 2000},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_catalog_product",
        "description": "Get trusted product details and variants from the app catalog.",
        "parameters": {
            "type": "object",
            "properties": {"product_id": {"type": "integer", "minimum": 1}},
            "required": ["product_id"],
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_product_stock",
        "description": "Get current stock for a product or exact variant. Use before saying a user can buy or draft a product.",
        "parameters": {
            "type": "object",
            "properties": {
                "product_id": {"type": "integer", "minimum": 1},
                "variant_id": {"type": "integer", "minimum": 1},
            },
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_my_basket",
        "description": "Get the current user's basket items and totals.",
        "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    {
        "type": "function",
        "name": "list_my_order_drafts",
        "description": "List recent order drafts for the current user.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "list_my_recent_orders",
        "description": "List recent final orders for the current user.",
        "parameters": {
            "type": "object",
            "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 10}},
            "additionalProperties": False,
        },
    },
    {
        "type": "function",
        "name": "get_my_order_details",
        "description": "Get details for one final order that belongs to the current user.",
        "parameters": {
            "type": "object",
            "properties": {"order_id": {"type": "integer", "minimum": 1}},
            "required": ["order_id"],
            "additionalProperties": False,
        },
    },
]

def _money(value: Decimal | int | float | None) -> str: return str(value or Decimal("0.00"))
def _product_summary(product: Product) -> dict[str, Any]:
    return {
        "product_id": product.id,
        "sku": product.sku,
        "name": product.name,
        "description": product.description,
        "usage": product.usage,
        "expiration": product.expiration,
        "in_stock": product.in_stock,
        "image_url": product.image_url,
        "variants": [_variant_summary(variant) for variant in product.variants if not variant.archived],
    }
def _variant_summary(variant: Variant) -> dict[str, Any]:
    return {
        "variant_id": variant.id,
        "product_id": variant.product_id,
        "sku": variant.sku,
        "name": variant.name,
        "stock": max(0, variant.stock),
        "in_stock": variant.stock > 0,
        "price": _money(variant.price),
        "image_url": variant.image_url,
    }
def _order_summary(order: Order) -> dict[str, Any]:
    return {
        "order_id": order.id,
        "code": getattr(order, "order_code", None),
        "status": getattr(order, "status", None),
        "payment_status": getattr(order, "payment_status", None),
        "grand_total": _money(getattr(order, "grand_total", None)),
        "currency": getattr(order, "currency", "RUB"),
        "created_at": getattr(order, "created_at", None),
        "items": [
            {
                "product_name": item.product_name,
                "variant_name": item.variant_name,
                "quantity": item.quantity,
                "line_total": _money(item.line_total),
            }
            for item in getattr(order, "items", [])
        ],
    }


class ShopAIToolExecutor:
    def __init__(self, session: AsyncSession, *, user_id: int) -> None:
        self._session = session
        self._user_id = user_id
        self.calls: list[dict[str, Any]] = []
        self.results: list[dict[str, Any]] = []

    async def execute(self, tool_name: str, arguments: ToolArguments | None = None) -> ToolArguments:
        started = time.monotonic()
        safe_arguments: ToolArguments = {}
        try:
            tool_method = self._get_tool_method(tool_name)
            safe_arguments = self._normalize_arguments(tool_name, arguments or {})
            result = await tool_method(**safe_arguments)

        except Exception as exc:
            self.calls.append(ShopAIToolCall(tool_name=tool_name, arguments=safe_arguments, ok=False, error=str(exc)[:500], duration_ms=int((time.monotonic() - started) * 1000)).__dict__)
            return {"ok": False, "error": "tool_execution_failed", "message": str(exc)[:500]}

        self.calls.append(ShopAIToolCall(tool_name=tool_name, arguments=safe_arguments, ok=True, duration_ms=int((time.monotonic() - started) * 1000)).__dict__)
        if isinstance(result, dict): self.results.append({"tool_name": tool_name, "arguments": safe_arguments, "result": result})
        return result

    def _get_tool_method(self, tool_name: str) -> ToolMethod:
        allowed_names = {tool["name"] for tool in SHOP_AI_FUNCTION_TOOLS}
        if tool_name not in allowed_names: raise ValueError(f"Unknown tool: {tool_name}")
        tool_method = getattr(self, tool_name, None)
        if not callable(tool_method): raise ValueError(f"Tool is not implemented: {tool_name}")
        return tool_method

    @staticmethod
    def _normalize_arguments(tool_name: str, arguments: ToolArguments) -> ToolArguments:
        if tool_name == "search_catalog_products":
            query = str(arguments.get("query") or "").strip()
            return {
                "query": query[:200],
                "limit": _clamped_int(arguments.get("limit"), default=20, minimum=1, maximum=50),
                "offset": _clamped_int(arguments.get("offset"), default=0, minimum=0, maximum=2000),
            }
        if tool_name in {"get_catalog_product"}: return {"product_id": _positive_int(arguments.get("product_id"), "product_id")}
        if tool_name == "get_product_stock":
            normalized: ToolArguments = {}
            if arguments.get("product_id") is not None: normalized["product_id"] = _positive_int(arguments.get("product_id"), "product_id")
            if arguments.get("variant_id") is not None: normalized["variant_id"] = _positive_int(arguments.get("variant_id"), "variant_id")
            if not normalized: raise ValueError("product_id or variant_id is required")
            return normalized
        if tool_name in {"list_my_order_drafts", "list_my_recent_orders"}: return {"limit": _clamped_int(arguments.get("limit"), default=5, minimum=1, maximum=10)}
        if tool_name == "get_my_order_details": return {"order_id": _positive_int(arguments.get("order_id"), "order_id")}
        return {}

    async def search_catalog_products(self, *, query: str, limit: int, offset: int) -> ToolArguments:
        stmt = select(Product).options(selectinload(Product.variants)).where(Product.archived.is_(False))
        if query:
            pattern = f"%{query}%"
            stmt = stmt.where(
                or_(
                    Product.name.ilike(pattern),
                    Product.sku.ilike(pattern),
                    Product.description.ilike(pattern),
                )
            )
        stmt = stmt.order_by(Product.in_stock.desc(), Product.priority.desc(), Product.id.desc()).offset(offset).limit(limit)
        products = list((await self._session.execute(stmt)).scalars().all())
        return {"ok": True, "query": query, "limit": limit, "offset": offset, "items": [_product_summary(product) for product in products]}

    async def get_catalog_product(self, *, product_id: int) -> ToolArguments:
        stmt = select(Product).options(selectinload(Product.variants)).where(Product.id == product_id, Product.archived.is_(False))
        product = (await self._session.execute(stmt)).scalar_one_or_none()
        if product is None: return {"ok": False, "error": "product_not_found"}
        return {"ok": True, "product": _product_summary(product)}

    async def get_product_stock(self, *, product_id: int | None = None, variant_id: int | None = None) -> ToolArguments:
        if variant_id is not None:
            stmt = select(Variant).options(selectinload(Variant.product)).where(Variant.id == variant_id)
            variant = (await self._session.execute(stmt)).scalar_one_or_none()
            if variant is None or variant.archived: return {"ok": False, "error": "variant_not_found"}
            if variant.product.archived: return {"ok": False, "error": "variant_not_found"}
            return {"ok": True, "scope": "variant", "variant": _variant_summary(variant)}

        stmt = select(Product).options(selectinload(Product.variants)).where(Product.id == product_id, Product.archived.is_(False))
        product = (await self._session.execute(stmt)).scalar_one_or_none()
        if product is None: return {"ok": False, "error": "product_not_found"}
        variants = [_variant_summary(variant) for variant in product.variants if not variant.archived]
        return {
            "ok": True,
            "scope": "product",
            "product_id": product.id,
            "in_stock": any(item["in_stock"] for item in variants),
            "variants": variants,
        }

    async def get_my_basket(self) -> ToolArguments:
        stmt = select(Basket).options(selectinload(Basket.items).selectinload(BasketItem.product), selectinload(Basket.items).selectinload(BasketItem.variant)).where(Basket.user_id == self._user_id)
        basket = (await self._session.execute(stmt)).scalar_one_or_none()
        if basket is None: return {"ok": True, "items": [], "total_quantity": 0, "total_amount": "0.00"}

        total_quantity = 0
        total_amount = Decimal("0.00")
        items: list[dict[str, Any]] = []
        for item in basket.items:
            line_total = item.variant.price * item.quantity
            total_quantity += item.quantity
            total_amount += line_total
            items.append(
                {
                    "product_id": item.product_id,
                    "variant_id": item.variant_id,
                    "product_name": item.product.name,
                    "variant_name": item.variant.name,
                    "quantity": item.quantity,
                    "line_total": _money(line_total),
                }
            )
        return {"ok": True, "items": items, "total_quantity": total_quantity, "total_amount": _money(total_amount)}

    async def list_my_order_drafts(self, *, limit: int) -> ToolArguments:
        stmt = select(OrderDraft).options(selectinload(OrderDraft.items)).where(OrderDraft.user_id == self._user_id).order_by(desc(OrderDraft.created_at), desc(OrderDraft.id)).limit(limit)
        drafts = list((await self._session.execute(stmt)).scalars().all())
        return {
            "ok": True,
            "items": [
                {
                    "draft_id": draft.id,
                    "draft_name": draft.draft_name,
                    "items_count": draft.items_count,
                    "total_quantity": draft.total_quantity,
                    "grand_total": _money(draft.grand_total),
                    "items": [
                        {
                            "product_name": item.product_name,
                            "variant_name": item.variant_name,
                            "quantity": item.quantity,
                        }
                        for item in draft.items
                    ],
                }
                for draft in drafts
            ],
        }

    async def list_my_recent_orders(self, *, limit: int) -> ToolArguments:
        stmt = select(Order).options(selectinload(Order.items)).where(Order.user_id == self._user_id).order_by(desc(Order.created_at), desc(Order.id)).limit(limit)
        orders = list((await self._session.execute(stmt)).scalars().all())
        return {"ok": True, "items": [_order_summary(order) for order in orders]}

    async def get_my_order_details(self, *, order_id: int) -> ToolArguments:
        stmt = select(Order).options(selectinload(Order.items)).where(Order.id == order_id, Order.user_id == self._user_id)
        order = (await self._session.execute(stmt)).scalar_one_or_none()
        if order is None: return {"ok": False, "error": "order_not_found"}
        return {"ok": True, "order": _order_summary(order)}


def _positive_int(value: Any, name: str) -> int:
    try: parsed = int(value)
    except (TypeError, ValueError) as exc: raise ValueError(f"{name} must be an integer") from exc
    if parsed <= 0: raise ValueError(f"{name} must be positive")
    return parsed


def _clamped_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try: parsed = int(value)
    except (TypeError, ValueError): parsed = default
    return max(minimum, min(maximum, parsed))


def tool_output_json(payload: Any) -> str: return json.dumps(payload, ensure_ascii=False, default=str)
