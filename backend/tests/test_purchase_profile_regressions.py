import asyncio
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import FastAPI, HTTPException
from httpx import ASGITransport, AsyncClient
from pydantic import ValidationError
from sqlalchemy import create_engine, update
from sqlalchemy.orm import Session
from starlette.requests import Request

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me import basket as basket_routes
from src.app.modules.users.me.profile import update_my_personal_data
from src.app.modules.users.me.schemas.order_draft import (
    UpdateOrderDraftPayload,
    UpdateOrderDraftRecipientPayload,
)
from src.app.modules.users.me.schemas.profile import PersonalDataUpdatePayload
from src.app.services import basket as basket_service
from src.app.services.delivery_quotes import build_bitrix_delivery_items
from src.app.services.orders import drafts, recipients
from src.app.services.stock_visibility import StockVisibilityPolicy
from src.database import Base, get_db
from src.database.models import (
    Basket, BasketItem, DeliveryAddress, DeliveryRecipient, OrderDraft,
    OrderDraftItem, Product, ProductByCategory, ProductCategory, User, Variant,
)


class AsyncSessionAdapter:
    def __init__(self, session):
        self.session = session

    async def execute(self, statement):
        return self.session.execute(statement)

    async def get(self, model, key):
        return self.session.get(model, key)

    async def flush(self):
        self.session.flush()

    async def commit(self):
        self.session.commit()

    async def rollback(self):
        self.session.rollback()

    async def refresh(self, instance):
        self.session.refresh(instance)


@pytest.fixture
def db():
    engine = create_engine("sqlite://")
    models = (
        User, Basket, BasketItem, DeliveryAddress, DeliveryRecipient, OrderDraft,
        OrderDraftItem, Product, Variant, ProductCategory, ProductByCategory,
    )
    Base.metadata.create_all(engine, tables=[model.__table__ for model in models])
    with Session(engine, autoflush=False, expire_on_commit=False) as session:
        session.add_all([
            User(id=1, username="synthetic", email="profile@example.com", name="Profile",
                 surname="Tester", phone_number="+79990000001", password_hash="unused"),
            User(id=2, username="other", email="other@example.com", name="Other",
                 surname="Tester", phone_number="+79990000002", password_hash="unused"),
        ])
        session.commit()
        yield AsyncSessionAdapter(session)
    engine.dispose()


@pytest.mark.parametrize("phone", ["+\u0667\u0669\u0669\u0669\u0661\u0662\u0663\u0664\u0665\u0666\u0667", "\uff17\uff19\uff19\uff19\uff11\uff12\uff13\uff14\uff15\uff16\uff17"])
def test_recipient_payload_rejects_non_ascii_phone_digits(phone):
    with pytest.raises(ValidationError):
        UpdateOrderDraftRecipientPayload(
            name="Recipient", surname="Tester", phone=phone, email="recipient@example.com",
        )


def test_recipient_payload_normalizes_formatted_phone_and_email():
    value = UpdateOrderDraftRecipientPayload(
        name=" Recipient ", surname=" Tester ", phone="+7 (999) 123-45-67",
        email="Recipient@EXAMPLE.COM",
    )
    assert value.phone == "+79991234567"
    assert value.email == "recipient@example.com"
    assert value.name == "Recipient"


@pytest.mark.parametrize("method,path,body", [
    ("POST", "/basket/items", {"variant_id": 11, "quantity": 1}),
    ("PATCH", "/basket/items/5", {"quantity": 2}),
])
def test_basket_api_rejects_archived_variant_before_any_write(monkeypatch, method, path, body):
    db = SimpleNamespace(commit=AsyncMock())
    basket = SimpleNamespace(id=3)
    variant = SimpleNamespace(id=11, product_id=7, archived=True, stock=20, price=Decimal("10.00"))
    monkeypatch.setattr(basket_routes, "_ensure_basket", AsyncMock(return_value=basket))
    monkeypatch.setattr(basket_routes, "get_basket_item_by_id", AsyncMock(
        return_value=SimpleNamespace(id=5, variant_id=11, quantity=1),
    ))
    monkeypatch.setattr(basket_routes, "_get_variant_for_update", AsyncMock(return_value=variant))
    monkeypatch.setattr(basket_routes, "_get_product_for_pricing", AsyncMock(
        return_value=SimpleNamespace(is_visible_in_app=True),
    ))
    monkeypatch.setattr(basket_routes, "require_catalog_products", AsyncMock())
    monkeypatch.setattr(basket_routes, "get_stock_visibility_policy", AsyncMock(return_value=StockVisibilityPolicy()))
    monkeypatch.setattr(basket_routes, "get_basket_item_by_basket_and_variant", AsyncMock(return_value=None))
    writes = [AsyncMock(), AsyncMock()]
    monkeypatch.setattr(basket_routes, "create_basket_item", writes[0])
    monkeypatch.setattr(basket_routes, "update_basket_item", writes[1])
    monkeypatch.setattr(basket_routes, "record_cart_add", AsyncMock())
    monkeypatch.setattr(basket_routes, "record_customer_event_safe", AsyncMock())
    now = datetime.now(timezone.utc)
    monkeypatch.setattr(basket_routes, "_get_serialized_basket", AsyncMock(return_value={
        "id": 3, "user_id": 1, "items": [], "items_count": 0, "total_quantity": 0,
        "total_amount": "0.00", "delivery_total": "0.00", "grand_total": "0.00",
        "currency": "RUB", "has_unavailable_items": False, "created_at": now, "updated_at": now,
    }))
    app = FastAPI()
    app.include_router(basket_routes.my_basket_router)
    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_current_user] = lambda: SimpleNamespace(id=1)

    async def run():
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.request(method, path, json=body)
            assert response.status_code == 404, response.text
            assert response.json()["detail"] == "Variant not found"

    asyncio.run(run())
    for write in writes:
        write.assert_not_awaited()
    db.commit.assert_not_awaited()


def test_basket_marks_archived_variant_unavailable_without_changing_totals():
    now = datetime.now(timezone.utc)
    product = Product(id=7, sku="synthetic-product", name="Product", in_stock=True)
    product.products_by_category = []
    variant = Variant(id=11, product_id=7, name="Archived variant", stock=20,
                      price=Decimal("10.00"), archived=True)
    basket = Basket(id=3, user_id=1, delivery_total=Decimal("5.00"), currency="RUB",
                    created_at=now, updated_at=now)
    basket.items = [BasketItem(id=5, variant_id=11, quantity=2, product=product,
                               variant=variant, created_at=now, updated_at=now)]
    request = Request({"type": "http", "headers": [], "scheme": "https", "server": ("example.test", 443)})
    result = basket_service.serialize_basket(request, basket, user=SimpleNamespace(id=1))
    assert result.has_unavailable_items is True
    assert result.items[0].is_available is False
    assert result.total_amount == Decimal("20.00")
    assert result.grand_total == Decimal("25.00")


def test_locked_variant_refreshes_a_previously_loaded_basket_line(db):
    product = Product(id=7, sku="synthetic", name="Product")
    variant = Variant(id=11, product=product, name="Variant", stock=20, price=Decimal("10.00"), archived=False)
    db.session.add_all([product, variant])
    db.session.commit()
    db.session.execute(update(Variant).where(Variant.id == 11).values(archived=True)
                       .execution_options(synchronize_session=False))
    assert variant.archived is False
    locked = asyncio.run(basket_service._get_variant_for_update(db, 11))
    assert locked.archived is True


def test_profile_patch_persists_normalized_fields_and_preserves_omitted_phone(db):
    user = db.session.get(User, 1)
    result = asyncio.run(update_my_personal_data(
        PersonalDataUpdatePayload(name=" Updated ", surname=" Person "), db=db, current_user=user,
    ))
    assert (result.name, result.surname) == ("Updated", "Person")
    db.session.expire_all()
    user = db.session.get(User, 1)
    assert (user.name, user.surname, user.phone_number) == ("Updated", "Person", "+79990000001")
    asyncio.run(update_my_personal_data(
        PersonalDataUpdatePayload(phone_number=None), db=db, current_user=user,
    ))
    db.session.expire_all()
    assert db.session.get(User, 1).phone_number is None


def test_profile_rejects_another_accounts_phone_without_persisting_partial_update(db):
    user = db.session.get(User, 1)
    with pytest.raises(HTTPException) as error:
        asyncio.run(update_my_personal_data(
            PersonalDataUpdatePayload(name="Not persisted", phone_number="+7 (999) 000-00-02"),
            db=db, current_user=user,
        ))
    assert error.value.status_code == 409
    # Match the rollback performed by the request's get_db dependency.
    db.session.rollback()
    assert db.session.get(User, 1).name == "Profile"
    assert db.session.get(User, 1).phone_number == "+79990000001"


def test_saved_recipient_selection_is_owned_and_profile_snapshot_stays_hidden(db):
    user = db.session.get(User, 1)
    snapshot = DeliveryRecipient(id=10, user_id=1, name="Profile", surname="Tester",
                                phone=user.phone_number, email=user.email, is_profile_snapshot=True)
    saved = DeliveryRecipient(id=11, user_id=1, name="Profile", surname="Tester",
                             phone="+79990000003", email="recipient@example.com", is_profile_snapshot=False)
    foreign = DeliveryRecipient(id=12, user_id=2, name="Other", surname="Recipient",
                               phone="+79990000004", email="foreign@example.com", is_profile_snapshot=False)
    db.session.add_all([snapshot, saved, foreign])
    db.session.commit()

    async def run():
        assert await recipients.resolve_checkout_recipient_selection(
            db, user=user, payload=UpdateOrderDraftPayload(recipient_id=saved.id),
        ) == saved.id
        assert await recipients.resolve_checkout_recipient_selection(
            db, user=user, payload=UpdateOrderDraftPayload(recipient_id=None),
        ) is None
        with pytest.raises(HTTPException) as error:
            await recipients.resolve_checkout_recipient_selection(
                db, user=user, payload=UpdateOrderDraftPayload(recipient_id=foreign.id),
            )
        assert error.value.status_code == 404
        await update_my_personal_data(PersonalDataUpdatePayload(name="Changed"), db=db, current_user=user)
        assert recipients.saved_checkout_recipient(snapshot, user) is None
        assert recipients.saved_checkout_recipient(saved, user) is saved
        options = await recipients.get_checkout_recipients(db, user=user, selected=saved, limit=20)
        assert [option.id for option in options] == [saved.id]
        assert snapshot.name == "Profile"

    asyncio.run(run())


def test_sync_empty_basket_to_cdek_draft_does_not_request_empty_quote(db, monkeypatch):
    address = DeliveryAddress(id=20, user_id=1, mode="pickup", provider="CDEK", country_code="RU",
                              name="Synthetic pickup", full_address="Synthetic address",
                              latitude=55.0, longitude=37.0)
    draft = OrderDraft(id=30, user_id=1, delivery_address=address, status="draft", items_count=1,
                       total_quantity=2, basket_subtotal=Decimal("20.00"), delivery_total=Decimal("199.00"),
                       grand_total=Decimal("219.00"), currency="RUB")
    draft.items = [OrderDraftItem(id=40, user_id=1, product_id=7, variant_id=11,
                                 product_name="Product", product_sku="synthetic", variant_name="Variant",
                                 quantity=2, unit_price=Decimal("10.00"), line_total=Decimal("20.00"))]
    db.session.add_all([address, draft, Basket(id=3, user_id=1)])
    db.session.commit()

    async def strict_quote(session, *, items, **kwargs):
        await build_bitrix_delivery_items(session, items)
        raise AssertionError("An empty draft must not reach a delivery provider")

    quote = AsyncMock(side_effect=strict_quote)
    monkeypatch.setattr(drafts, "calculate_authoritative_cdek_quote", quote)
    result = asyncio.run(drafts.update_order_draft_for_user(
        db, user=db.session.get(User, 1), draft_id=draft.id,
        payload=UpdateOrderDraftPayload(sync_basket_items=True),
    ))
    assert result.items == []
    assert result.items_count == result.total_quantity == 0
    assert result.basket_subtotal == Decimal("0.00")
    assert result.grand_total == result.delivery_total == Decimal("199.00")
    quote.assert_not_awaited()
