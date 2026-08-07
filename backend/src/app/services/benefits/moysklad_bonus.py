import logging
from dataclasses import dataclass
from decimal import Decimal, ROUND_FLOOR
from typing import Any
from uuid import UUID

from src.database.models import User
from src.integrations.moysklad.client import MoySkladClient, get_moysklad_client
from src.normalize import coerce_uuid, optional_str

from .money import quantize_money

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class MoySkladBonusWallet:
    is_loaded: bool = False
    counterparty_id: UUID | None = None
    program_id: UUID | None = None
    program_name: str | None = None
    balance_points: int = 0
    balance_rubles: Decimal = Decimal("0.00")
    spend_rate_points_to_ruble: int = 1
    max_paid_rate_percent: Decimal = Decimal("0.00")
    sales_amount_rubles: Decimal = Decimal("0.00")

    @property
    def is_available(self) -> bool:
        return (
            self.counterparty_id is not None
            and self.program_id is not None
            and self.balance_points > 0
            and self.balance_rubles > Decimal("0.00")
            and self.max_paid_rate_percent > Decimal("0.00")
        )


def _uuid_from_entity(value: Any) -> UUID | None:
    if not isinstance(value, dict):
        return None
    direct = coerce_uuid(value.get("id"))
    if direct is not None:
        return direct
    meta = value.get("meta")
    href = optional_str(meta.get("href")) if isinstance(meta, dict) else None
    return coerce_uuid(href.rstrip("/").rsplit("/", 1)[-1]) if href else None


def _nonnegative_int(value: Any, *, default: int = 0) -> int:
    try:
        return max(0, int(Decimal(str(value))))
    except (TypeError, ValueError, ArithmeticError):
        return default


def _nonnegative_decimal(value: Any) -> Decimal:
    try:
        return max(Decimal("0.00"), Decimal(str(value)))
    except (TypeError, ValueError, ArithmeticError):
        return Decimal("0.00")


def bonus_points_to_rubles(points: int, spend_rate_points_to_ruble: int) -> Decimal:
    rate = max(1, int(spend_rate_points_to_ruble))
    return quantize_money(Decimal(max(0, int(points))) / Decimal(rate)) or Decimal("0.00")


def bonus_wallet_from_counterparty(counterparty: dict[str, Any] | None) -> MoySkladBonusWallet:
    if not isinstance(counterparty, dict):
        return MoySkladBonusWallet()

    program = counterparty.get("bonusProgram")
    program = program if isinstance(program, dict) else {}
    counterparty_id = coerce_uuid(counterparty.get("id"))
    program_id = _uuid_from_entity(program)
    balance_points = _nonnegative_int(counterparty.get("bonusPoints"))
    spend_rate = max(1, _nonnegative_int(program.get("spendRatePointsToRouble"), default=1))
    # The app's loyalty terms allow paying the full merchandise total with
    # accumulated points. MoySklad remains the balance ledger, while checkout
    # owns this redemption cap.
    max_paid_rate = Decimal("100.00") if program_id is not None else Decimal("0.00")
    if program.get("active") is False:
        max_paid_rate = Decimal("0.00")
    sales_amount_minor = _nonnegative_decimal(counterparty.get("salesAmount"))

    return MoySkladBonusWallet(
        is_loaded=True,
        counterparty_id=counterparty_id,
        program_id=program_id,
        program_name=optional_str(program.get("name")),
        balance_points=balance_points,
        balance_rubles=bonus_points_to_rubles(balance_points, spend_rate),
        spend_rate_points_to_ruble=spend_rate,
        max_paid_rate_percent=max_paid_rate,
        sales_amount_rubles=quantize_money(sales_amount_minor / Decimal("100")) or Decimal("0.00"),
    )


async def get_user_moysklad_bonus_wallet(
    user: User,
    *,
    moysklad_client: MoySkladClient | None = None,
) -> MoySkladBonusWallet:
    client = moysklad_client or get_moysklad_client()
    if user.moysklad_counterparty_id is None or not client.is_configured():
        return MoySkladBonusWallet()

    try:
        return await get_moysklad_bonus_wallet(
            user.moysklad_counterparty_id,
            moysklad_client=client,
        )
    except Exception:
        logger.exception(
            "Could not load MoySklad bonus wallet user_id=%s counterparty_id=%s",
            user.id,
            user.moysklad_counterparty_id,
        )
        return MoySkladBonusWallet()


async def get_moysklad_bonus_wallet(
    counterparty_id: UUID,
    *,
    moysklad_client: MoySkladClient | None = None,
) -> MoySkladBonusWallet:
    client = moysklad_client or get_moysklad_client()
    if not client.is_configured():
        return MoySkladBonusWallet()

    counterparty = await client.get_counterparty(
        counterparty_id,
        expand_bonus_program=True,
    )
    if not isinstance(counterparty, dict):
        return MoySkladBonusWallet()

    program = counterparty.get("bonusProgram")
    program_id = _uuid_from_entity(program)
    if (
        program_id is not None
        and isinstance(program, dict)
        and program.get("spendRatePointsToRouble") is None
    ):
        expanded_program = await client.get_bonus_program(program_id)
        if expanded_program is not None:
            counterparty = {**counterparty, "bonusProgram": expanded_program}
    return bonus_wallet_from_counterparty(counterparty)


def bonus_spend_for_subtotal(
    wallet: MoySkladBonusWallet,
    subtotal: Decimal,
) -> tuple[int, Decimal]:
    normalized_subtotal = quantize_money(subtotal) or Decimal("0.00")
    if not wallet.is_available or normalized_subtotal <= Decimal("0.00"):
        return 0, Decimal("0.00")

    maximum_rubles = quantize_money(
        normalized_subtotal * wallet.max_paid_rate_percent / Decimal("100")
    ) or Decimal("0.00")
    maximum_points = int(
        (maximum_rubles * Decimal(wallet.spend_rate_points_to_ruble)).to_integral_value(
            rounding=ROUND_FLOOR
        )
    )
    points_to_spend = min(wallet.balance_points, max(0, maximum_points))
    rubles_to_spend = min(
        normalized_subtotal,
        bonus_points_to_rubles(points_to_spend, wallet.spend_rate_points_to_ruble),
    )
    return points_to_spend, rubles_to_spend
