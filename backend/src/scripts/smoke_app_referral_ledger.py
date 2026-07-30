from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import delete, select
from sqlalchemy.orm import selectinload

from src.app.services.referrals.paid_orders import sync_paid_order_referral_to_app
from src.database import SessionLocal
from src.database.models import (
    AppReferralPurchase,
    DeliveryAddress,
    DeliveryRecipient,
    Order,
    User,
)
from src.integrations.bitrix_promo import BitrixPromoClient


async def main() -> None:
    suffix = os.environ.get("ELIXIR_REFERRAL_SMOKE_SUFFIX", "").strip().upper()
    if not suffix or not suffix.isalnum() or len(suffix) > 24:
        raise RuntimeError("ELIXIR_REFERRAL_SMOKE_SUFFIX must contain 1-24 letters or digits")

    email = f"buyer-{suffix.lower()}@example.invalid"
    promo = f"{suffix}-REFERRER"
    order_code = f"SMOKE-{suffix}"[:24]
    user_id = address_id = recipient_id = order_id = None

    async with SessionLocal() as session:
        existing = (
            await session.execute(
                select(User.id).where(User.email == email).limit(1)
            )
        ).scalar_one_or_none()
        if existing is not None:
            raise RuntimeError("Smoke customer already exists; clean the previous run first")

        try:
            user = User(
                email=email,
                password_hash="smoke-test-not-a-login",
                name="Elixir",
                surname="Smoke Buyer",
                is_active=True,
                is_verified=True,
                promo_code=promo,
            )
            session.add(user)
            await session.flush()
            user_id = user.id

            address = DeliveryAddress(
                user_id=user.id,
                mode="door",
                provider="CDEK",
                country_code="RU",
                name="Referral smoke",
                full_address="Referral smoke test address",
                city="Moscow",
                latitude=55.75,
                longitude=37.61,
            )
            recipient = DeliveryRecipient(
                user_id=user.id,
                name="Elixir",
                surname="Smoke Buyer",
                phone="",
                email=email,
            )
            session.add_all([address, recipient])
            await session.flush()
            address_id = address.id
            recipient_id = recipient.id

            paid_at = datetime.now(timezone.utc)
            order = Order(
                user_id=user.id,
                delivery_address_id=address.id,
                recipient_id=recipient.id,
                order_code=order_code,
                status="Оплачен",
                items_count=1,
                total_quantity=1,
                basket_subtotal=Decimal("12500.00"),
                delivery_total=Decimal("0.00"),
                grand_total=Decimal("12500.00"),
                currency="RUB",
                checkout_snapshot={
                    "benefits": {
                        "applications": [
                            {
                                "source_kind": "bitrix_promo",
                                "code": promo,
                                "discount_percent": "3.00",
                            }
                        ]
                    }
                },
                payment_status="paid",
                payment_paid_at=paid_at,
                is_paid=True,
            )
            session.add(order)
            await session.commit()
            order_id = order.id

            result = await sync_paid_order_referral_to_app(session, order=order)
            stored = (
                await session.execute(
                    select(AppReferralPurchase)
                    .options(selectinload(AppReferralPurchase.accruals))
                    .where(AppReferralPurchase.order_id == order.id)
                )
            ).scalar_one()
            amounts = sorted(
                (row.level, str(row.commission_amount), row.status)
                for row in stored.accruals
            )
            if (
                result is None
                or stored.bitrix_sync_status != "synced"
                or amounts != [(1, "2125.00", "pending"), (2, "375.00", "pending")]
                or result.get("bitrix", {}).get("coupon_usage", {}).get("source")
                != "app_paid_order"
            ):
                raise RuntimeError(
                    f"Unexpected referral ledger result: result={result!r}, "
                    f"sync={stored.bitrix_sync_status!r}, accruals={amounts!r}"
                )

            promo_client = BitrixPromoClient()
            usage_after_first = int((await promo_client.lookup(promo)).get("use_count") or 0)
            bitrix_replay = await promo_client.record_paid_purchase(
                external_order_id=order_code,
                user_email=email,
                promo=promo,
                amount=str(order.grand_total),
                currency=order.currency,
                paid_at=paid_at.isoformat(),
            )
            usage_after_replay = int((await promo_client.lookup(promo)).get("use_count") or 0)
            if (
                bitrix_replay.get("outcome") != "already_recorded"
                or usage_after_replay != usage_after_first
            ):
                raise RuntimeError(
                    "Idempotent Bitrix retry changed coupon usage statistics: "
                    f"replay={bitrix_replay!r}, before={usage_after_first}, "
                    f"after={usage_after_replay}"
                )

            duplicate = await sync_paid_order_referral_to_app(session, order=order)
            duplicate_stored = (
                await session.execute(
                    select(AppReferralPurchase)
                    .options(selectinload(AppReferralPurchase.accruals))
                    .where(AppReferralPurchase.order_id == order.id)
                )
            ).scalar_one()
            if duplicate is None or len(duplicate_stored.accruals) != 2:
                raise RuntimeError("Idempotent retry changed the app referral ledger")

            print(
                json.dumps(
                    {
                        "ok": True,
                        "storage": "app",
                        "purchase_sync": stored.bitrix_sync_status,
                        "accruals": amounts,
                        "coupon_use_count": usage_after_replay,
                        "duplicate_accrual_count": len(duplicate_stored.accruals),
                    },
                    ensure_ascii=False,
                )
            )
        finally:
            await session.rollback()
            if order_id is not None:
                await session.execute(delete(Order).where(Order.id == order_id))
            if address_id is not None:
                await session.execute(
                    delete(DeliveryAddress).where(DeliveryAddress.id == address_id)
                )
            if recipient_id is not None:
                await session.execute(
                    delete(DeliveryRecipient).where(DeliveryRecipient.id == recipient_id)
                )
            if user_id is not None:
                await session.execute(delete(User).where(User.id == user_id))
            await session.commit()


if __name__ == "__main__":
    asyncio.run(main())
