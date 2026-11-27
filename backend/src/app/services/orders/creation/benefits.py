from decimal import Decimal
from typing import Any
import httpx
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from config import ufa_now
from src.app.services.benefits.service import resolve_benefits_for_user
from src.database.models import Order, OrderBenefitApplication, RewardProgramSelectionEvent as Event, User
from src.integrations.moysklad.client import get_moysklad_client


async def _verify_order_referral(session, user, resolved):
    from src.app.services.benefits.settlement import PROGRAM_ATTRIBUTE_ID, PROGRAM_NAMES, REFERRER_ATTRIBUTE_ID, DISCOUNT_ATTRIBUTE_ID

    code = resolved["ms_order_promo"]
    buyer = user.moysklad_counterparty_id
    # Two app checkouts must not choose different first referrers while robot 10 is pending.
    await session.execute(select(func.pg_advisory_xact_lock(func.hashtextextended(f"order-promo:{buyer}", 0))))
    try:
        card = await get_moysklad_client().get_counterparty(buyer)
        if not card or str(card["id"]) != str(buyer) or card.get("archived"):
            raise ValueError("Missing buyer")
        attrs = {a["id"]: a.get("value") for a in card.get("attributes", [])}
        program = PROGRAM_NAMES.get(str((attrs.get(PROGRAM_ATTRIBUTE_ID) or {}).get("name", "")).strip().casefold())
        rate = attrs.get(DISCOUNT_ATTRIBUTE_ID)
        if isinstance(rate, dict):
            rate = rate.get("name")
        rate = Decimal(str(rate or 0).strip().removesuffix("%").replace(",", "."))
        incoming = str(attrs.get(REFERRER_ATTRIBUTE_ID) or "").strip().casefold()
    except (httpx.HTTPError, RuntimeError, ValueError, ArithmeticError, KeyError, AttributeError) as exc:
        raise HTTPException(503, "Не удалось перепроверить условия МойСклада. Заказ не создан.") from exc
    expected = resolved["ms_promo_buyer_state"]
    if (program != expected["program"] or incoming != str(expected["incoming"] or "").strip().casefold()
            or rate != Decimal(str(expected["discount"] or 0))):
        raise HTTPException(409, "Условия покупателя в МойСкладе изменились. Обновите расчёт.")
    if not incoming:
        if not any(o["source_kind"] == "app_referral" and o["applied_discount_amount"] > 0
                   for o in resolved["stacked_discount_options"]):
            raise HTTPException(422, "В заказе нет товаров, на которые действует промокод.")
        recorded = Order.checkout_snapshot["benefits"]["ms_order_promo"].as_string()
        # Orders from a previously closed referral relationship must remain in history,
        # but must not prevent this buyer starting a new relationship.
        cutoff = select(func.max(Event.created_at)).where(Event.user_id == User.id,
            Event.source == "promo_unlink", Event.snapshot["buyer"].as_string() == str(buyer),
            Event.snapshot["done"].as_boolean().is_(True)).correlate(User).scalar_subquery()
        conflict = await session.scalar(select(Order.id).join(User, User.id == Order.user_id).where(
            User.moysklad_counterparty_id == buyer, Order.is_canceled.is_(False),
            cutoff.is_(None) | (Order.created_at >= cutoff),
            func.lower(recorded) != code.lower()).limit(1))
        if conflict:
            raise HTTPException(409, "Другой заказ уже передан с другим промокодом. Дождитесь обновления МойСклада.")


async def _persist_order_benefit_applications(session: AsyncSession, *, order: Order, user: User, resolved_benefits: dict[str, Any]) -> None:
    now = ufa_now()
    applications: list[OrderBenefitApplication] = []

    for option in resolved_benefits.get("stacked_discount_options", []):
        source_kind = option.get("source_kind")
        source_record_id = option.get("source_record_id")
        if source_kind == "app_welcome":
            from src.app.services.benefits.app_welcome import verify_reservation
            await verify_reservation(session, user.id, option["applied_discount_amount"])
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


async def _resolve_checkout_benefits(session: AsyncSession, *, user: User, subtotal: Decimal, discountable_subtotal: Decimal, delivery_total: Decimal, currency: str, entered_code: str | None, quote_items: list[dict[str, Any]], use_bonus_rubles: bool, bonus_rubles_to_use: Decimal | None = None, reward_mode: str | None, mobile_welcome: bool = False) -> dict[str, Any]:
    resolved = await resolve_benefits_for_user(session, user=user, entered_code=entered_code, subtotal=subtotal, discountable_subtotal=discountable_subtotal, delivery_total=delivery_total, currency=currency, quote_items=quote_items, use_bonus_rubles=use_bonus_rubles, bonus_rubles_to_use=bonus_rubles_to_use, reward_mode=reward_mode, mobile_welcome=mobile_welcome)
    if resolved.get("ms_order_promo"):
        await _verify_order_referral(session, user, resolved)
    if use_bonus_rubles and resolved.get("balance_redemption_mode") != "automatic" and not (resolved.get("bonus_option") or {}).get("is_applicable"): raise HTTPException(409, "Баланс недоступен или изменился. Обновите оформление заказа.")
    return resolved
