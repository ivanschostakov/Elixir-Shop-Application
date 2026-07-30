from copy import deepcopy
from decimal import Decimal
import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Order, OrderBenefitApplication, User
from src.integrations.moysklad.client import MoySkladClient, get_moysklad_client
from src.normalize import coerce_uuid, optional_str

from .money import quantize_money

BONUS_SOURCE_KIND = "moysklad_bonus"
logger = logging.getLogger(__name__)


async def _bonus_application(
    session: AsyncSession,
    *,
    order_id: int,
) -> OrderBenefitApplication | None:
    return (
        await session.execute(
            select(OrderBenefitApplication)
            .where(
                OrderBenefitApplication.order_id == order_id,
                OrderBenefitApplication.source_kind == BONUS_SOURCE_KIND,
            )
            .order_by(OrderBenefitApplication.id.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


def _failed_checkout_snapshot(
    checkout_snapshot: dict[str, Any] | None,
    *,
    restored_amount: Decimal,
    error: str,
) -> dict[str, Any]:
    snapshot = deepcopy(checkout_snapshot) if isinstance(checkout_snapshot, dict) else {}
    benefits = snapshot.get("benefits")
    benefits = deepcopy(benefits) if isinstance(benefits, dict) else {}
    applications = benefits.get("applications")
    benefits["applications"] = [
        application
        for application in (applications if isinstance(applications, list) else [])
        if not (
            isinstance(application, dict)
            and application.get("source_kind") == BONUS_SOURCE_KIND
        )
    ]
    stacked_discount = Decimal(str(benefits.get("stacked_discount_amount") or 0))
    total_after = Decimal(str(benefits.get("total_after_discounts") or 0))
    benefits["stacked_discount_amount"] = float(
        quantize_money(max(Decimal("0.00"), stacked_discount - restored_amount))
        or Decimal("0.00")
    )
    benefits["total_after_discounts"] = float(
        quantize_money(total_after + restored_amount) or Decimal("0.00")
    )
    benefits["bonus_applied_points"] = 0
    benefits["bonus_applied_rubles"] = 0.0
    benefits["use_bonus_rubles"] = False
    benefits["bonus_redemption_error"] = error
    snapshot["benefits"] = benefits
    return snapshot


async def redeem_order_bonus_safe(
    session: AsyncSession,
    *,
    order: Order,
    user: User,
    moysklad_client: MoySkladClient | None = None,
) -> bool:
    application = await _bonus_application(session, order_id=order.id)
    if application is None:
        return True
    if application.external_reference:
        return True

    program_id = coerce_uuid(application.source_external_id)
    counterparty_id = user.moysklad_counterparty_id
    points = int(Decimal(str(application.benefit_units or 0)))
    client = moysklad_client or get_moysklad_client()

    try:
        if program_id is None or counterparty_id is None or points <= 0:
            raise ValueError("Incomplete MoySklad bonus redemption data")
        if not client.is_configured():
            raise RuntimeError("MoySklad is not configured")

        transaction = await client.resolve_or_create_bonus_transaction(
            counterparty_id=counterparty_id,
            bonus_program_id=program_id,
            bonus_points=points,
            transaction_type="SPENDING",
            external_code=f"elixir-bonus-spend-{order.order_code}",
            name=f"Списание бонусов по заказу {order.order_code}",
            description=f"Заказ приложения {order.order_code}",
        )
        if optional_str(transaction.get("transactionType")) not in {None, "SPENDING"}:
            raise RuntimeError("MoySklad returned a different bonus transaction type")
        if transaction.get("applicable") is False or transaction.get("transactionStatus") == "CANCELED":
            raise RuntimeError("MoySklad canceled the bonus spending transaction")
        transaction_id = optional_str(transaction.get("id"))
        if transaction_id is None:
            raise RuntimeError("MoySklad bonus transaction has no id")

        application.external_reference = transaction_id
        application.status = "applied"
        calculation_snapshot = deepcopy(application.calculation_snapshot or {})
        calculation_snapshot["moysklad_bonus_transaction_id"] = transaction_id
        calculation_snapshot["moysklad_bonus_transaction_type"] = "SPENDING"
        application.calculation_snapshot = calculation_snapshot
        await session.commit()
        return True
    except Exception as exc:
        logger.exception(
            "Could not redeem MoySklad bonus points order_id=%s user_id=%s",
            order.id,
            user.id,
        )
        await session.rollback()

        application = await _bonus_application(session, order_id=order.id)
        persisted_order = await session.get(Order, order.id)
        if application is None or persisted_order is None:
            return False

        restored_amount = quantize_money(application.discount_amount) or Decimal("0.00")
        error = optional_str(str(exc)) or "MoySklad bonus redemption failed"
        application.status = "failed"
        calculation_snapshot = deepcopy(application.calculation_snapshot or {})
        calculation_snapshot["redemption_error"] = error
        application.calculation_snapshot = calculation_snapshot
        persisted_order.grand_total = (
            quantize_money(persisted_order.grand_total + restored_amount)
            or persisted_order.grand_total
        )
        persisted_order.checkout_snapshot = _failed_checkout_snapshot(
            persisted_order.checkout_snapshot,
            restored_amount=restored_amount,
            error=error,
        )
        await session.commit()
        return False


async def reverse_order_bonus_safe(
    session: AsyncSession,
    *,
    order: Order,
    user: User,
    moysklad_client: MoySkladClient | None = None,
) -> bool:
    application = await _bonus_application(session, order_id=order.id)
    if application is None or application.status == "reversed":
        return True
    if application.status != "applied" or not application.external_reference:
        return True

    program_id = coerce_uuid(application.source_external_id)
    counterparty_id = user.moysklad_counterparty_id
    points = int(Decimal(str(application.benefit_units or 0)))
    client = moysklad_client or get_moysklad_client()

    try:
        if program_id is None or counterparty_id is None or points <= 0:
            raise ValueError("Incomplete MoySklad bonus reversal data")
        if not client.is_configured():
            raise RuntimeError("MoySklad is not configured")

        transaction = await client.resolve_or_create_bonus_transaction(
            counterparty_id=counterparty_id,
            bonus_program_id=program_id,
            bonus_points=points,
            transaction_type="EARNING",
            external_code=f"elixir-bonus-return-{order.order_code}",
            name=f"Возврат бонусов по заказу {order.order_code}",
            description=f"Возврат или отмена заказа приложения {order.order_code}",
        )
        if optional_str(transaction.get("transactionType")) not in {None, "EARNING"}:
            raise RuntimeError("MoySklad returned a different bonus return transaction type")
        if transaction.get("applicable") is False or transaction.get("transactionStatus") == "CANCELED":
            raise RuntimeError("MoySklad canceled the bonus return transaction")
        transaction_id = optional_str(transaction.get("id"))
        if transaction_id is None:
            raise RuntimeError("MoySklad bonus return transaction has no id")

        application.status = "reversed"
        calculation_snapshot = deepcopy(application.calculation_snapshot or {})
        calculation_snapshot["moysklad_bonus_return_transaction_id"] = transaction_id
        calculation_snapshot["moysklad_bonus_return_transaction_type"] = "EARNING"
        application.calculation_snapshot = calculation_snapshot
        await session.commit()
        return True
    except Exception:
        logger.exception(
            "Could not return MoySklad bonus points order_id=%s user_id=%s",
            order.id,
            user.id,
        )
        await session.rollback()
        return False
