import logging
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Literal
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.app.services.benefits.moysklad_bonus import (
    MoySkladBonusWallet,
    get_moysklad_bonus_wallet,
)
from src.database.models import AppReferralAccrual, AppReferralPurchase, User
from src.integrations.moysklad.client import MoySkladClient, get_moysklad_client
from src.normalize import coerce_uuid, optional_str

from .calculations import quantize_money

logger = logging.getLogger(__name__)

WalletSyncOutcome = Literal[
    "credited",
    "reversed",
    "not_applicable",
    "waiting_for_wallet",
]


class BonusWalletNotReady(RuntimeError):
    pass


def bonus_points_for_rubles(
    amount_rubles: Decimal,
    spend_rate_points_to_ruble: int,
) -> int:
    return max(
        0,
        int(
            (
                Decimal(amount_rubles)
                * Decimal(max(1, int(spend_rate_points_to_ruble)))
            ).to_integral_value(rounding=ROUND_HALF_UP)
        ),
    )


def _transaction_id(
    transaction: dict[str, object],
    *,
    expected_type: str,
) -> UUID:
    transaction_type = optional_str(transaction.get("transactionType"))
    if transaction_type is not None and transaction_type.upper() != expected_type:
        raise RuntimeError(
            f"MoySklad returned {transaction_type} instead of {expected_type}"
        )
    if (
        transaction.get("applicable") is False
        or transaction.get("transactionStatus") == "CANCELED"
    ):
        raise RuntimeError("MoySklad canceled the bonus transaction")
    transaction_id = coerce_uuid(transaction.get("id"))
    if transaction_id is None:
        raise RuntimeError("MoySklad bonus transaction has no valid id")
    return transaction_id


async def _local_beneficiary(
    db: AsyncSession,
    accrual: AppReferralAccrual,
) -> User | None:
    user = (
        await db.get(User, accrual.beneficiary_user_id)
        if accrual.beneficiary_user_id is not None
        else None
    )
    email = optional_str(accrual.beneficiary_email)
    if user is None and email:
        user = (
            await db.execute(
                select(User)
                .where(func.lower(User.email) == email.casefold())
                .limit(1)
            )
        ).scalar_one_or_none()
        if user is not None:
            accrual.beneficiary_user_id = user.id
    return user


async def _resolve_wallet(
    db: AsyncSession,
    accrual: AppReferralAccrual,
    client: MoySkladClient,
) -> MoySkladBonusWallet:
    user = await _local_beneficiary(db, accrual)
    counterparty_id = (
        user.moysklad_counterparty_id if user is not None else None
    )
    email = optional_str(
        user.email if user is not None and user.email else accrual.beneficiary_email
    )
    if counterparty_id is None and email:
        counterparty = await client.get_counterparty_by_email(email)
        counterparty_id = (
            coerce_uuid(counterparty.get("id"))
            if isinstance(counterparty, dict)
            else None
        )
        if user is not None and counterparty_id is not None:
            user.moysklad_counterparty_id = counterparty_id

    if counterparty_id is None:
        raise BonusWalletNotReady(
            "Не найден контрагент МойСклад для получателя начисления"
        )

    wallet = await get_moysklad_bonus_wallet(
        counterparty_id,
        moysklad_client=client,
    )
    if wallet.counterparty_id is None or wallet.program_id is None:
        raise BonusWalletNotReady(
            "У контрагента МойСклад не подключена бонусная программа"
        )
    return wallet


async def _credit_accrual(
    db: AsyncSession,
    accrual: AppReferralAccrual,
    client: MoySkladClient,
) -> WalletSyncOutcome:
    if (
        accrual.wallet_sync_status == "credited"
        and accrual.moysklad_bonus_transaction_id is not None
    ):
        return "credited"
    if str(accrual.currency).upper() != "RUB":
        raise RuntimeError(
            f"Нельзя зачислить начисление в валюте {accrual.currency} как бонусные рубли"
        )

    wallet = await _resolve_wallet(db, accrual, client)
    points = bonus_points_for_rubles(
        accrual.commission_amount,
        wallet.spend_rate_points_to_ruble,
    )
    if points <= 0:
        accrual.wallet_sync_status = "not_applicable"
        accrual.wallet_sync_error = None
        return "not_applicable"

    transaction = await client.resolve_or_create_bonus_transaction(
        counterparty_id=wallet.counterparty_id,
        bonus_program_id=wallet.program_id,
        bonus_points=points,
        transaction_type="EARNING",
        external_code=f"elixir-partner-accrual-{accrual.id}",
        name=f"Партнёрское начисление {accrual.purchase.external_order_id}",
        description=(
            f"Подтверждённое партнёрское начисление уровня {accrual.level} "
            f"по заказу приложения {accrual.purchase.external_order_id}"
        ),
    )
    transaction_id = _transaction_id(transaction, expected_type="EARNING")
    credited_rubles = quantize_money(
        Decimal(points) / Decimal(wallet.spend_rate_points_to_ruble)
    ) or Decimal("0.00")

    accrual.wallet_sync_status = "credited"
    accrual.moysklad_counterparty_id = wallet.counterparty_id
    accrual.moysklad_bonus_program_id = wallet.program_id
    accrual.moysklad_bonus_transaction_id = transaction_id
    accrual.bonus_points_credited = points
    accrual.bonus_rubles_credited = credited_rubles
    accrual.wallet_synced_at = datetime.now(timezone.utc)
    accrual.wallet_sync_error = None
    return "credited"


async def _reverse_accrual(
    accrual: AppReferralAccrual,
    client: MoySkladClient,
) -> WalletSyncOutcome:
    if accrual.wallet_reversal_transaction_id is not None:
        accrual.wallet_sync_status = "reversed"
        return "reversed"
    if (
        accrual.moysklad_counterparty_id is None
        or accrual.moysklad_bonus_program_id is None
        or not accrual.bonus_points_credited
    ):
        accrual.wallet_sync_status = "not_applicable"
        accrual.wallet_sync_error = None
        return "not_applicable"

    transaction = await client.resolve_or_create_bonus_transaction(
        counterparty_id=accrual.moysklad_counterparty_id,
        bonus_program_id=accrual.moysklad_bonus_program_id,
        bonus_points=accrual.bonus_points_credited,
        transaction_type="SPENDING",
        external_code=f"elixir-partner-accrual-reversal-{accrual.id}",
        name=f"Отмена партнёрского начисления {accrual.purchase.external_order_id}",
        description=(
            f"Возврат или отмена заказа приложения "
            f"{accrual.purchase.external_order_id}"
        ),
    )
    transaction_id = _transaction_id(transaction, expected_type="SPENDING")
    accrual.wallet_sync_status = "reversed"
    accrual.wallet_reversal_transaction_id = transaction_id
    accrual.wallet_reversed_at = datetime.now(timezone.utc)
    accrual.wallet_sync_error = None
    return "reversed"


async def sync_referral_accrual_to_bonus_wallet(
    db: AsyncSession,
    *,
    accrual: AppReferralAccrual,
    moysklad_client: MoySkladClient | None = None,
) -> WalletSyncOutcome:
    client = moysklad_client or get_moysklad_client()
    if not client.is_configured():
        raise BonusWalletNotReady("Интеграция МойСклад не настроена")

    if accrual.status == "approved":
        try:
            return await _credit_accrual(db, accrual, client)
        except BonusWalletNotReady as error:
            accrual.wallet_sync_status = "waiting_for_wallet"
            accrual.wallet_sync_error = str(error)[:500]
            return "waiting_for_wallet"
    if accrual.status == "rejected":
        return await _reverse_accrual(accrual, client)

    accrual.wallet_sync_status = "not_applicable"
    accrual.wallet_sync_error = None
    return "not_applicable"


async def sync_approved_referral_accruals_to_bonus_wallet(
    db: AsyncSession,
    *,
    limit: int = 200,
    moysklad_client: MoySkladClient | None = None,
) -> dict[str, int]:
    client = moysklad_client or get_moysklad_client()
    if not client.is_configured():
        return {
            "processed": 0,
            "credited": 0,
            "reversed": 0,
            "waiting": 0,
            "failed": 0,
        }

    row_ids = list(
        (
            await db.execute(
                select(AppReferralAccrual.id)
                .where(
                    or_(
                        and_(
                            AppReferralAccrual.status == "approved",
                            AppReferralAccrual.wallet_sync_status.in_(
                                ("pending", "waiting_for_wallet", "failed")
                            ),
                        ),
                        and_(
                            AppReferralAccrual.status == "rejected",
                            AppReferralAccrual.wallet_sync_status.in_(
                                (
                                    "pending",
                                    "waiting_for_wallet",
                                    "failed",
                                    "credited",
                                    "reversal_failed",
                                )
                            ),
                        ),
                    )
                )
                .order_by(AppReferralAccrual.id)
                .limit(max(1, min(limit, 1000)))
            )
        ).scalars().all()
    )
    counters = {
        "processed": 0,
        "credited": 0,
        "reversed": 0,
        "waiting": 0,
        "failed": 0,
    }
    for row_id in row_ids:
        try:
            accrual = (
                await db.execute(
                    select(AppReferralAccrual)
                    .options(selectinload(AppReferralAccrual.purchase))
                    .where(AppReferralAccrual.id == row_id)
                    .with_for_update()
                )
            ).scalar_one()
            outcome = await sync_referral_accrual_to_bonus_wallet(
                db,
                accrual=accrual,
                moysklad_client=client,
            )
            await db.commit()
            counters["processed"] += 1
            if outcome == "credited":
                counters["credited"] += 1
            elif outcome == "reversed":
                counters["reversed"] += 1
            elif outcome == "waiting_for_wallet":
                counters["waiting"] += 1
        except Exception as error:
            await db.rollback()
            accrual = await db.get(AppReferralAccrual, row_id)
            if accrual is not None:
                accrual.wallet_sync_status = (
                    "reversal_failed"
                    if accrual.status == "rejected"
                    and accrual.moysklad_bonus_transaction_id is not None
                    else "failed"
                )
                accrual.wallet_sync_error = (
                    optional_str(str(error)) or "Неизвестная ошибка синхронизации"
                )[:500]
                await db.commit()
            counters["failed"] += 1
            logger.exception(
                "Could not sync referral accrual to MoySklad wallet accrual_id=%s",
                row_id,
            )
    return counters
