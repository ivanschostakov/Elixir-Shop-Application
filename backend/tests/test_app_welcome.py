import asyncio
from datetime import timedelta
from decimal import Decimal
from types import SimpleNamespace
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import Session

from config import ufa_now
from src.app.services.benefits import app_welcome
from src.database import engine
from src.database.models import LoyaltyBonusCredit, OrderBenefitApplication, User
from src.integrations.moysklad.order_sync.positions import _build_customerorder_positions
from test_orders_api import (registered_user, variant_factory, stub_amocrm, sync_engine,
                             _create_ready_draft, _update_order)


def seed(uid):
    now = ufa_now()
    with Session(sync_engine) as db:
        db.add(LoyaltyBonusCredit(user_id=uid, idempotency_key=f"welcome:user:{uid}", source_kind="app_welcome",
               points=1000, status="local", earned_at=now, available_at=now, expires_at=now+timedelta(days=5)))
        db.commit()


def test_checkout_reserves_only_goods_and_releases_unpaid_cancel(client, registered_user, variant_factory, stub_amocrm):
    uid = registered_user["user_id"]
    seed(uid)
    headers = {**registered_user["headers"], "X-App-Platform": "android"}
    variant = variant_factory(price=Decimal("400.01"))
    draft = _create_ready_draft(client, headers, variant["variant_id"])
    def quote(payload, platform="android"):
        r = client.post("/api/v1/users/me/benefits/check", headers={**headers, "X-App-Platform": platform}, json=payload)
        assert r.status_code == 200, r.text
        return r.json()
    assert Decimal(quote({"draft_id": draft["id"]}, "web")["welcome_balance_rubles"]) == 0
    q = quote({"draft_id": draft["id"]})
    assert Decimal(q["welcome_balance_rubles"]) == 1000
    row, = [x for x in q["stacked_discount_options"] if x["source_kind"] == "app_welcome"]
    assert Decimal(row["applied_discount_amount"]) == Decimal("400.01")
    r = client.post("/api/v1/users/me/orders", headers=headers, json={"draft_id":draft["id"], "payment_method":"later"})
    assert r.status_code == 200, r.text
    o = r.json()
    assert Decimal(str(o["grand_total"])) == Decimal("400.01") + Decimal(str(o["delivery_total"]))
    assert Decimal(quote({"subtotal": "800"})["welcome_balance_rubles"]) == Decimal("599.99")
    _update_order(o["id"], is_canceled=True)
    assert Decimal(quote({"subtotal": "800"})["welcome_balance_rubles"]) == 1000
    with Session(sync_engine) as db:
        db.query(LoyaltyBonusCredit).filter_by(user_id=uid).one().expires_at = ufa_now()
        db.commit()
    assert Decimal(quote({"subtotal": "800"})["welcome_balance_rubles"]) == 0


def test_order_directly_from_mobile_basket(client, registered_user, variant_factory, stub_amocrm):
    from test_orders_api import _build_pickup_payload
    seed(registered_user["user_id"])
    headers = {**registered_user["headers"], "X-App-Platform": "android"}
    vid = variant_factory(price=Decimal("1500"))["variant_id"]
    assert client.post("/api/v1/users/me/basket/items", headers=headers, json={"variant_id":vid, "quantity":2}).is_success
    checkout = client.patch("/api/v1/users/me/basket/checkout", headers=headers, json={
        "new_delivery_address":_build_pickup_payload(), "new_recipient":{
            "name":"Test","surname":"User","phone":"+79991234567","email":"test@example.com"}})
    assert checkout.is_success, checkout.text
    r = client.post("/api/v1/users/me/orders", headers=headers, json={"payment_method":"later"})
    assert r.status_code == 200, r.text
    assert Decimal(str(r.json()["grand_total"])) == Decimal("2000") + Decimal(str(r.json()["delivery_total"]))


def test_two_reservations_cannot_spend_the_same_credit(client, registered_user, variant_factory, stub_amocrm):
    uid = registered_user["user_id"]
    seed(uid)
    from test_orders_api import _create_order_for_history
    oid = _create_order_for_history(client, registered_user["headers"], variant_factory()["variant_id"])["id"]
    async def run():
        pool = create_async_engine(engine.url)
        sessions = async_sessionmaker(pool)
        async def reserve():
            async with sessions() as db:
                try:
                    await app_welcome.verify_reservation(db, uid, Decimal("600"))
                except HTTPException as e:
                    return e.status_code
                db.add(OrderBenefitApplication(order_id=oid, user_id=uid, source_kind="app_welcome",
                       discount_amount=Decimal("600"), currency="RUB", calculation_snapshot={}))
                await db.commit()
                return 200
        try:
            assert sorted(await asyncio.gather(reserve(), reserve())) == [200, 409]
        finally:
            await pool.dispose()
    asyncio.run(run())


@pytest.mark.parametrize("goods,available,expected", [("99.99","1000","49.99"), ("0.01","1000","0"),
                                                     ("9000","1000","1000"), ("800","20.15","20.15")])
def test_cap(goods, available, expected):
    assert app_welcome.discount(Decimal(available), Decimal(goods)) == Decimal(expected)


@pytest.mark.parametrize("legacy", [False, True])
def test_grant_replay_never_renews_or_duplicates(registered_user, legacy):
    uid = registered_user["user_id"]
    if legacy:
        seed(uid)
        with Session(sync_engine) as db:
            old = db.query(LoyaltyBonusCredit).filter_by(user_id=uid).one()
            old.source_kind, old.status, old.expires_at = "welcome", "applied", None
            db.commit()
    async def run():
        pool = create_async_engine(engine.url)
        try:
            for _ in range(2):
                async with async_sessionmaker(pool)() as db:
                    await app_welcome.grant_on_email_confirmation(db, await db.get(User, uid))
                    await db.commit()
        finally:
            await pool.dispose()
    asyncio.run(run())
    with Session(sync_engine) as db:
        credit = db.query(LoyaltyBonusCredit).filter_by(user_id=uid).one()
        assert credit.source_kind == ("welcome" if legacy else "app_welcome")
        if legacy:
            assert credit.expires_at is None and credit.status == "applied"
        else:
            assert credit.expires_at == credit.earned_at + timedelta(days=5)


@pytest.mark.parametrize("priced", [True, False])
def test_export_preserves_previous_discount_then_applies_welcome_to_goods(priced):
    items = [SimpleNamespace(variant_id=i, product_id=i, quantity=2, line_total=Decimal("100.00")) for i in (1, 2)]
    benefits = {"applications":[{"source_kind":"app_welcome","discount_amount":"90.00"}],
                "discount_excluded_product_ids":[2]}
    if priced:
        benefits["priced_items"] = [{"variant_id":i,"quantity":2,"line_total":str(amount)} for i, amount in [(1,80),(2,100)]]
    order = SimpleNamespace(items=items, basket_subtotal=Decimal("200"), delivery_total=Decimal("300"),
                            grand_total=Decimal("390"), checkout_snapshot={"benefits":benefits})
    rows, missing = _build_customerorder_positions(moysklad_client=SimpleNamespace(build_customerorder_position=lambda **kw:kw),
        assortment_refs={1:("variant",uuid4()),2:("variant",uuid4())}, order=order)
    assert not missing and [r["quantity"]*r["unit_price"] for r in rows] == [Decimal("40"),Decimal("50")]
