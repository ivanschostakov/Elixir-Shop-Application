from decimal import Decimal
from typing import Any
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from config import ufa_now
from src.app.services.benefits.service import resolve_benefits_for_user
from src.database.models import Order, OrderBenefitApplication, User


async def _persist_order_benefit_applications(session: AsyncSession, *, order: Order, user: User, resolved_benefits: dict[str, Any]) -> None:
    now = ufa_now()
    applications: list[OrderBenefitApplication] = []

    for option in resolved_benefits.get("stacked_discount_options", []):
        source_kind = option.get("source_kind")
        source_record_id = option.get("source_record_id")
        kwargs: dict[str, Any] = {}
        if source_kind == "app_referral": kwargs["referral_profile_id"] = source_record_id

        snapshot = {
            "sequence": option.get("sequence"),
            "subtotal_before": str(option.get("subtotal_before")),
            "subtotal_after": str(option.get("subtotal_after")),
            "entered_code": resolved_benefits.get("entered_code"),
            "benefit_unit_name": option.get("benefit_unit_name"),
        }
        if source_kind == "app_referral":
            snapshot.update(
                {
                    "promo_code": option.get("code"),
                }
            )

        applications.append(OrderBenefitApplication(order_id=order.id, user_id=user.id, source_kind=source_kind, source_external_id=option.get("source_external_id"), entered_code=resolved_benefits.get("entered_code"), resolved_code=option.get("code"), discount_percent=option.get("discount_percent"), discount_amount=option.get("applied_discount_amount"), benefit_units=option.get("benefit_units"), currency=option.get("currency") or resolved_benefits.get("currency") or order.currency, status="pending" if source_kind == "moysklad_settlement" else "applied", applied_at=now, calculation_snapshot=snapshot, **kwargs,))

    if applications:
        session.add_all(applications)
        await session.flush()


async def _resolve_checkout_benefits(session: AsyncSession, *, user: User, subtotal: Decimal, discountable_subtotal: Decimal, delivery_total: Decimal, currency: str, entered_code: str | None, quote_items: list[dict[str, Any]], use_bonus_rubles: bool, reward_mode: str | None,) -> dict[str, Any]:
    resolved = await resolve_benefits_for_user(session, user=user, entered_code=entered_code, subtotal=subtotal, discountable_subtotal=discountable_subtotal, delivery_total=delivery_total, currency=currency, quote_items=quote_items, use_bonus_rubles=use_bonus_rubles, reward_mode=reward_mode,)
    if use_bonus_rubles and not (resolved.get("bonus_option") or {}).get("is_applicable"): raise HTTPException(409, "Баланс недоступен или изменился. Обновите оформление заказа.")
    return resolved
