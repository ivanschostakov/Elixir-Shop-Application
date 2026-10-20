from decimal import Decimal
from typing import Any
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.database.models import AppReferralAccrual, AppReferralPurchase, ReferralProfile, User
from src.normalize import optional_str
from .calculations import _local_user_id_for_email


async def _create_local_accrual_from_bitrix(db: AsyncSession, *, purchase: AppReferralPurchase, raw_accrual: dict[str, Any],) -> AppReferralAccrual | None:
    beneficiary_bitrix_user_id = int(raw_accrual.get("beneficiary_user_id") or 0)
    level = int(raw_accrual.get("level") or 0)
    if beneficiary_bitrix_user_id <= 0 or level <= 0: return None

    raw_beneficiary = raw_accrual.get("beneficiary")
    raw_beneficiary = (raw_beneficiary if isinstance(raw_beneficiary, dict) else {})
    beneficiary_email = optional_str(raw_beneficiary.get("email"))
    beneficiary_user_id = (await db.execute(select(ReferralProfile.user_id).where(ReferralProfile.bitrix_user_id == beneficiary_bitrix_user_id).limit(1))).scalar_one_or_none()
    if beneficiary_user_id is None: beneficiary_user_id = await _local_user_id_for_email(db, beneficiary_email,)
    beneficiary = (await db.get(User, beneficiary_user_id) if beneficiary_user_id is not None else None)
    if beneficiary is not None and beneficiary.email: beneficiary_email = beneficiary.email
    eligibility = raw_accrual.get("eligibility")
    eligibility = eligibility if isinstance(eligibility, dict) else {}
    row = AppReferralAccrual(purchase_id=purchase.id, beneficiary_user_id=beneficiary_user_id, beneficiary_bitrix_user_id=beneficiary_bitrix_user_id, beneficiary_email=beneficiary_email, beneficiary_name=(optional_str(" ".join(part for part in (getattr(beneficiary, "name", ""), getattr(beneficiary, "surname", ""),) if part)) if beneficiary is not None else optional_str(raw_beneficiary.get("name"))), bitrix_accrual_id=(int(raw_accrual["id"]) if raw_accrual.get("id") else None), referral_bitrix_user_id=int(raw_accrual.get("referral_user_id") or 0), level=level, buyer_discount_percent=Decimal(str(raw_accrual.get("buyer_discount_percent") or 0)), referrer_discount_percent=Decimal(str(raw_accrual.get("referrer_discount_percent") or 0)), commission_percent=Decimal(str(raw_accrual.get("percent") or 0)), commission_amount=Decimal(str(raw_accrual.get("amount") or 0)), currency=str(raw_accrual.get("currency") or purchase.currency), status=str(raw_accrual.get("status") or "pending"), reason=optional_str(raw_accrual.get("reason")), eligibility_snapshot=eligibility,)
    db.add(row)
    return row
