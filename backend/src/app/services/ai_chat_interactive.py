from __future__ import annotations

import base64
import copy
import hashlib
import hmac
import json
import time
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import AI_CHAT_ACTION_SECRET, AI_CHAT_ACTION_TOKEN_TTL_SECONDS
from src.database.models import Product, Variant
from src.database.schemas import (
    AIInteractiveAction,
    AIInteractivePayload,
    AIInteractiveProductCard,
    AIInteractiveVariant,
)


ProductRequestedAction = Literal["open_product", "compare", "alternatives"]
ProductRefIntent = Literal["recommend", "compare", "alternative"]


class StructuredProductRef(BaseModel):
    model_config = ConfigDict(extra="forbid")

    product_id: int = Field(gt=0)
    variant_id: int | None = Field(default=None, gt=0)
    intent: ProductRefIntent = "recommend"
    reason: str = Field(min_length=1, max_length=500)
    requested_actions: list[ProductRequestedAction] = Field(default_factory=list, max_length=3)


class StructuredBasketItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    variant_id: int = Field(gt=0)
    quantity: int = Field(ge=1, le=100)


class StructuredBasketAddition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[StructuredBasketItem] = Field(default_factory=list, min_length=1, max_length=10)


class StructuredAIChatOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    assistant_text: str = Field(min_length=1, max_length=12000)
    product_refs: list[StructuredProductRef] = Field(default_factory=list, max_length=6)
    basket_addition: StructuredBasketAddition | None = None


class AIActionTokenPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    v: Literal[1] = 1
    user_id: int = Field(gt=0)
    chat_id: int = Field(gt=0)
    message_id: int = Field(gt=0)
    action_id: str = Field(min_length=1, max_length=120)
    expires_at: int = Field(gt=0)


def _normalize_openai_json_schema(node: Any) -> Any:
    if isinstance(node, dict):
        normalized = {
            key: _normalize_openai_json_schema(value)
            for key, value in node.items()
            if key not in {"default", "title"}
        }
        properties = normalized.get("properties")
        if isinstance(properties, dict):
            normalized["type"] = "object"
            normalized["required"] = list(properties.keys())
            normalized["additionalProperties"] = False
        return normalized
    if isinstance(node, list):
        return [_normalize_openai_json_schema(item) for item in node]
    return node


def build_ai_chat_output_schema() -> dict[str, Any]:
    return _normalize_openai_json_schema(copy.deepcopy(StructuredAIChatOutput.model_json_schema()))


def parse_structured_ai_chat_output(payload: Any) -> StructuredAIChatOutput | None:
    if payload is None:
        return None
    try:
        if isinstance(payload, StructuredAIChatOutput):
            return payload
        if isinstance(payload, str):
            return StructuredAIChatOutput.model_validate_json(payload)
        if isinstance(payload, dict):
            return StructuredAIChatOutput.model_validate(payload)
    except ValidationError:
        return None
    return None


def load_ai_interactive_payload(context_json: dict[str, Any] | None) -> AIInteractivePayload | None:
    interactive = (context_json or {}).get("interactive")
    if not isinstance(interactive, dict):
        return None
    try:
        return AIInteractivePayload.model_validate(interactive)
    except ValidationError:
        return None


def _action_secret() -> str:
    if AI_CHAT_ACTION_SECRET:
        return AI_CHAT_ACTION_SECRET
    raise RuntimeError("AI_CHAT_ACTION_SECRET or JWT_ACCESS_SECRET_KEY must be configured")


def _urlsafe_b64encode(payload: bytes) -> str:
    return base64.urlsafe_b64encode(payload).decode("utf-8").rstrip("=")


def _urlsafe_b64decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(f"{value}{'=' * (-len(value) % 4)}".encode("utf-8"))


def _action_signature(encoded_payload: str) -> str:
    return hmac.new(_action_secret().encode("utf-8"), encoded_payload.encode("utf-8"), hashlib.sha256).hexdigest()


def mint_ai_action_token(*, user_id: int, chat_id: int, message_id: int, action_id: str) -> str:
    payload = AIActionTokenPayload(
        user_id=user_id,
        chat_id=chat_id,
        message_id=message_id,
        action_id=action_id,
        expires_at=int(time.time()) + max(1, int(AI_CHAT_ACTION_TOKEN_TTL_SECONDS)),
    )
    encoded_payload = _urlsafe_b64encode(payload.model_dump_json(exclude_none=True).encode("utf-8"))
    return f"{encoded_payload}.{_action_signature(encoded_payload)}"


def verify_ai_action_token(token: str) -> AIActionTokenPayload:
    encoded_payload, separator, signature = str(token or "").strip().partition(".")
    if not encoded_payload or not separator or not signature:
        raise ValueError("Invalid action token")
    if not hmac.compare_digest(signature, _action_signature(encoded_payload)):
        raise ValueError("Invalid action token signature")
    try:
        payload = AIActionTokenPayload.model_validate_json(_urlsafe_b64decode(encoded_payload).decode("utf-8"))
    except (ValidationError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError("Invalid action token payload") from exc
    if payload.expires_at < int(time.time()):
        raise ValueError("Action token expired")
    return payload


def _make_action_id(*parts: Any) -> str:
    raw = "_".join(str(part).strip().replace(" ", "_") for part in parts if str(part).strip())
    cleaned = "".join(char if char.isalnum() or char in {"_", "-"} else "_" for char in raw.lower())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_")[:120] or "action"


def _truncate(value: str | None, limit: int) -> str | None:
    text = str(value or "").strip()
    if not text:
        return None
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "..."


def _variant_image_url(variant: Variant) -> str:
    return variant.image_url or variant.product.image_url


async def _load_products(session: AsyncSession, product_ids: set[int]) -> dict[int, Product]:
    if not product_ids:
        return {}
    stmt = (
        select(Product)
        .options(selectinload(Product.variants))
        .where(Product.id.in_(product_ids))
    )
    products = list((await session.execute(stmt)).scalars().all())
    return {product.id: product for product in products}


async def _load_variants(session: AsyncSession, variant_ids: set[int]) -> dict[int, Variant]:
    if not variant_ids:
        return {}
    stmt = (
        select(Variant)
        .options(selectinload(Variant.product))
        .where(Variant.id.in_(variant_ids))
    )
    variants = list((await session.execute(stmt)).scalars().all())
    return {variant.id: variant for variant in variants}


def _build_product_card(product: Product, ref: StructuredProductRef) -> AIInteractiveProductCard:
    in_stock_variants = [variant for variant in product.variants if variant.stock > 0]
    shown_variants = in_stock_variants[:6]
    variant_rows = [
        AIInteractiveVariant(
            id=variant.id,
            sku=variant.sku,
            name=variant.name,
            stock=max(0, variant.stock),
            price=variant.price,
            image_url=_variant_image_url(variant),
            in_stock=variant.stock > 0,
        )
        for variant in shown_variants
    ]
    actions = [
        AIInteractiveAction(
            id=_make_action_id("product", product.id, "open"),
            type="open_product",
            label="Открыть товар",
            style="link",
            product_id=product.id,
        )
    ]

    for variant in shown_variants[:3]:
        actions.append(
            AIInteractiveAction(
                id=_make_action_id("product", product.id, "variant", variant.id),
                type="add_to_basket",
                label=f"Выбрать {variant.name}",
                style="secondary",
                product_id=product.id,
                variant_id=variant.id,
                quantity=1,
            )
        )

    if "compare" in ref.requested_actions:
        actions.append(
            AIInteractiveAction(
                id=_make_action_id("product", product.id, "compare"),
                type="ask_ai",
                label="Сравнить",
                prompt=f"Сравни {product.name} с похожими товарами из каталога.",
            )
        )
    if "alternatives" in ref.requested_actions:
        actions.append(
            AIInteractiveAction(
                id=_make_action_id("product", product.id, "alternatives"),
                type="ask_ai",
                label="Альтернативы",
                prompt=f"Подбери 2-3 альтернативы для {product.name} из каталога.",
            )
        )

    return AIInteractiveProductCard(
        id=_make_action_id("product", product.id),
        product_id=product.id,
        intent=ref.intent,
        title=product.name,
        reason=_truncate(ref.reason, 500),
        image_url=product.image_url,
        in_stock=bool(in_stock_variants),
        variants=variant_rows,
        actions=actions[:6],
    )


async def build_ai_interactive_payload(
    session: AsyncSession,
    structured_output: StructuredAIChatOutput,
) -> AIInteractivePayload | None:
    product_ids = {ref.product_id for ref in structured_output.product_refs}
    products_by_id = await _load_products(session, product_ids)

    cards: list[AIInteractiveProductCard] = []
    seen_product_ids: set[int] = set()
    for ref in structured_output.product_refs:
        product = products_by_id.get(ref.product_id)
        if product is None or product.id in seen_product_ids:
            continue
        seen_product_ids.add(product.id)
        cards.append(_build_product_card(product, ref))

    if not cards:
        return None

    return AIInteractivePayload(
        cards=cards,
    )


def attach_ai_action_tokens(
    interactive: AIInteractivePayload | None,
    *,
    user_id: int,
    chat_id: int,
    message_id: int,
) -> AIInteractivePayload | None:
    if interactive is None:
        return interactive

    updated = interactive.model_copy(deep=True)
    basket_actions: list[AIInteractiveAction] = []
    for card in updated.cards:
        basket_actions.extend(action for action in card.actions if action.type == "add_to_basket" and not action.completed)

    for action in basket_actions:
        action.action_token = mint_ai_action_token(
            user_id=user_id,
            chat_id=chat_id,
            message_id=message_id,
            action_id=action.id,
        )
    return updated


def find_ai_interactive_action(interactive: AIInteractivePayload, action_id: str) -> AIInteractiveAction | None:
    for card in interactive.cards:
        for action in card.actions:
            if action.id == action_id:
                return action
    return None
