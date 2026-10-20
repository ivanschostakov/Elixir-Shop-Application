from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from fastapi import HTTPException
from starlette import status
from src.app.services.benefits.money import quantize_money
from src.database.models import OrderDraft


def _json_money(value: Any) -> float:
    return float(quantize_money(value) or Decimal("0.00"))


def _json_safe_benefits(resolved_benefits: dict[str, Any] | None) -> dict[str, Any]:
    if resolved_benefits is None: return {}

    return {
        "entered_code": resolved_benefits.get("entered_code"),
        "reward_program": resolved_benefits.get("reward_program"),
        "reward_mode": resolved_benefits.get("reward_mode"),
        "basket_subtotal": _json_money(resolved_benefits.get("basket_subtotal")),
        "stacked_discount_amount": _json_money(resolved_benefits.get("stacked_discount_amount")),
        "total_after_discounts": _json_money(resolved_benefits.get("total_after_discounts")),
        "cash_total": _json_money(resolved_benefits["cash_total"]) if resolved_benefits.get("cash_total") is not None else None,
        "use_bonus_rubles": bool(resolved_benefits.get("use_bonus_rubles")),
        "bonus_applied_points": int(resolved_benefits.get("bonus_applied_points") or 0),
        "bonus_applied_rubles": _json_money(resolved_benefits.get("bonus_applied_rubles")),
        "cashback_percent": str(resolved_benefits.get("cashback_percent") or 0),
        "cashback_earned_points": int(resolved_benefits.get("cashback_earned_points") or 0),
        "cashback_expires_in_days": int(resolved_benefits.get("cashback_expires_in_days") or 0),
        "settlement_counterparty_id": resolved_benefits.get("settlement_counterparty_id"),
        "settlement_balance_rubles": str(resolved_benefits.get("settlement_balance_rubles") or 0),
        "applications": [
            {
                "source_kind": option.get("source_kind"),
                "code": option.get("code"),
                "discount_percent": str(option.get("discount_percent")) if option.get("discount_percent") is not None else None,
                "discount_amount": str(option.get("applied_discount_amount")) if option.get("applied_discount_amount") is not None else None,
                "sequence": option.get("sequence"),
                "source_external_id": option.get("source_external_id"),
                "benefit_units": str(option.get("benefit_units")) if option.get("benefit_units") is not None else None,
                "benefit_unit_name": option.get("benefit_unit_name"),
            }
            for option in resolved_benefits.get("stacked_discount_options", [])
        ],
    }


def _checkout_snapshot_item(item) -> dict[str, Any]:
    return {
        "id": item.product_id,
        "featureId": item.variant_id,
        "name": item.product_name,
        "product_name": item.product_name,
        "feature_name": item.variant_name,
        "code": item.product_sku,
        "qty": item.quantity,
        "price": float(item.unit_price),
        "subtotal": float(item.line_total),
    }


def _build_checkout_snapshot(draft: OrderDraft, *, payment_method: str, selected_delivery_service: str, selected_delivery_payload: dict[str, Any], resolved_benefits: dict[str, Any] | None = None, client_platform: str | None = None) -> dict[str, Any]:
    if draft.recipient is None: raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Recipient is required")
    items = [_checkout_snapshot_item(item) for item in draft.items]
    snapshot = {
        "source": "shop_application",
        "client_platform": client_platform if client_platform in {"ios", "android", "web"} else "unknown",
        "payment_method": payment_method,
        "contact_info": {
            "name": draft.recipient.name,
            "surname": draft.recipient.surname,
            "phone": draft.recipient.phone,
            "email": draft.recipient.email,
        },
        "checkout_data": {"items": items, "total": float(draft.basket_subtotal)},
        "benefits": _json_safe_benefits(resolved_benefits),
        "selected_delivery": deepcopy(selected_delivery_payload),
        "selected_delivery_service": selected_delivery_service,
        "commentary": draft.comment or "Не указан",
        "order_date": datetime.now(timezone.utc).isoformat(),
    }
    benefits = snapshot["benefits"]
    if benefits.get("settlement_counterparty_id") and benefits.get("use_bonus_rubles"):
        snapshot["settlement_payment"] = {
            "version": 1, "status": "awaiting_invoice",
            "counterparty_id": benefits["settlement_counterparty_id"],
            "maximum_balance_rubles": benefits["settlement_balance_rubles"],
            "gross_rubles": str(quantize_money(
                (Decimal(str(benefits["cash_total"])) if benefits.get("cash_total") is not None
                 else Decimal(str(benefits["total_after_discounts"])) + draft.delivery_total)
                + Decimal(str(benefits["bonus_applied_rubles"])))),
        }
    return snapshot
