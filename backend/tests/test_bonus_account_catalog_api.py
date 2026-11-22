from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.app.services.benefits.settlement_schemas import SettlementRead
from src.database.models import ReferralProfile, User
from test_orders_api import registered_user, sync_engine


def test_bonus_account_without_discount_can_load_basket_and_recommendations(
    client, registered_user, monkeypatch,
):
    counterparty_id = uuid4()
    user_id = registered_user["user_id"]
    with Session(sync_engine) as db:
        user = db.get(User, user_id)
        user.moysklad_counterparty_id = counterparty_id
        profile = db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user_id)).scalar_one_or_none()
        if profile is None:
            profile = ReferralProfile(user_id=user_id, current_discount_percent=Decimal("0.00"))
            db.add(profile)
        profile.reward_program = "bonus"
        profile.reward_program_selection_source = "moysklad"
        profile.reward_program_snapshot = {
            "moysklad_program_code": 1,
            "moysklad_counterparty_id": str(counterparty_id),
        }
        db.commit()

    settlement = SettlementRead(
        status="fresh", loyalty_program=1, personal_discount_percent=None,
        balance_rubles=Decimal("0"), total_purchases_rubles=Decimal("0"),
        fetched_at=datetime.now(timezone.utc),
    )
    monkeypatch.setattr("src.app.services.benefits.settlement.get_account_settlement",
        AsyncMock(return_value=settlement))

    for path in (
        "/api/v1/users/me/basket",
        "/api/v1/users/me/recommendations?surface=home&limit=8&offset=0",
    ):
        response = client.get(path, headers=registered_user["headers"])
        assert response.status_code == 200, response.text

    with Session(sync_engine) as db:
        profile = db.execute(select(ReferralProfile).where(ReferralProfile.user_id == user_id)).scalar_one()
        assert profile.reward_program == "bonus"
        assert profile.current_discount_percent == Decimal("0.00")
