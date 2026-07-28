from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, "/app/backend")

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.app.modules.auth.schemas.login import UserLoginPayload
from src.app.services.auth.service import _get_email_login_user
from src.database import SessionLocal
from src.database.models import Product, Variant
from src.integrations.bitrix_promo import BitrixPromoClient
from src.integrations.website_identity import WebsiteIdentityClient
from src.integrations.website_reviews import WebsiteReviewSyncClient


async def main() -> None:
    email = os.environ["ELIXIR_SMOKE_EMAIL"]
    password = os.environ["ELIXIR_SMOKE_PASSWORD"]
    promo = os.environ["ELIXIR_SMOKE_PROMO"]

    identity = await WebsiteIdentityClient().authenticate(login=email, password=password)
    identity_user = identity["user"]
    if str(identity_user.get("email", "")).lower() != email.lower():
        raise RuntimeError("Website identity email mismatch")

    promo_client = BitrixPromoClient()
    lookup = await promo_client.lookup(promo)
    if str(lookup.get("promo", "")).upper() != promo.upper():
        raise RuntimeError("Promo lookup mismatch")

    matched_quote = None
    async with SessionLocal() as db:
        variants = list(
            (
                await db.execute(
                    select(Variant)
                    .join(Product, Product.id == Variant.product_id)
                    .options(selectinload(Variant.product))
                    .where(Variant.archived.is_(False), Product.archived.is_(False), Variant.price > 0)
                    .order_by(Variant.id)
                    .limit(20)
                )
            ).scalars().all()
        )
        for variant in variants:
            quote = await promo_client.quote(
                promo=promo,
                user_email=email,
                items=[
                    {
                        "variant_system_id": str(variant.system_id),
                        "product_system_id": str(variant.product.system_id),
                        "sku": variant.sku or variant.product.sku,
                        "quantity": 1,
                    }
                ],
            )
            if quote.get("is_applicable"):
                matched_quote = quote
                break
        if matched_quote is None:
            raise RuntimeError("No real active product accepted the smoke promo")

        local_user = await _get_email_login_user(
            UserLoginPayload(login=email, password=password),
            db,
        )
        if local_user.email != email or not local_user.is_verified:
            raise RuntimeError("Website login fallback did not create a verified customer")
        await db.delete(local_user)
        await db.commit()

    review_page = await WebsiteReviewSyncClient().request("pull", {"offset": 0, "limit": 100})
    reviews = review_page.get("reviews")
    if not isinstance(reviews, list) or int(review_page.get("total") or 0) < 1:
        raise RuntimeError("Website review pull returned no real data")

    print(
        json.dumps(
            {
                "identity": "ok",
                "login_fallback": "ok",
                "promo_lookup": "ok",
                "promo_quote": "ok",
                "promo_discount_positive": float(matched_quote["discount_amount"]) > 0,
                "promo_user_context": matched_quote.get("user_context"),
                "promo_match": matched_quote["lines"][0].get("matched_by"),
                "website_review_total": int(review_page.get("total") or 0),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
