"""Transport integration using only the explicitly isolated companion_test database."""
import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select
from starlette.requests import Request

import config
from test_ai_companion_db import database, URL
from src.app.modules.telegram_ai.router import start, message, action, control, Start, MessageInput, CardInput, Control
from src.app.services.ai.companion import service
from src.database.models.ai.companion import AICompanionEntry
from src.integrations.ai.enums import BotModel

pytestmark = pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")


def test_telegram_roundtrip_confirmation_retry_and_erase(monkeypatch):
    import importlib
    route=importlib.import_module("src.app.modules.telegram_ai.router")
    limits=importlib.import_module("src.app.services.rate_limit")
    monkeypatch.setattr(config,"AI_COMPANION_ENABLED",True)
    monkeypatch.setattr(config,"AI_COMPANION_DIALOGUE_ENABLED",True)
    monkeypatch.setattr(limits,"enforce_rate_limit",AsyncMock())
    lock=SimpleNamespace(acquire=AsyncMock(return_value=True),owned=AsyncMock(return_value=True),release=AsyncMock())
    monkeypatch.setattr(route,"get_cache_service",lambda:SimpleNamespace(client=SimpleNamespace(lock=lambda *a,**kw:lock)))
    seen={}
    async def respond(**kwargs):
        seen.update(kwargs)
        return {"text":"Проверьте запись", "structured_output":{"assistant_text":"Проверьте запись", "companion_dialogue":{"operations":[{"kind":"entry","summary":"Вес 80 кг","evidence":"Вес 80 кг","certain":False,"entry":{"kind":"weight","weight_kg":"80","occurred_at":datetime.now(timezone.utc).isoformat()}}]}},"openai_model":"mock","input_tokens":100,"output_tokens":10,"conversation_id":kwargs["conversation_id"]}
    professor=SimpleNamespace(create_conversation=AsyncMock(return_value="conv_tg_test"),send_message_v2=AsyncMock(side_effect=respond),_resolve_model_name=lambda _:"mock")
    monkeypatch.setattr(route,"get_professor_client",lambda:professor)
    async def run():
        async with database() as (db,user):
            user.telegram_user_id=88000000001
            await db.flush()
            result=await start(Start(telegram_user_id=user.telegram_user_id,request_key="start-telegram-test",adult_confirmed=True),db)
            assert result["timezone"]=="Europe/Moscow"
            request=Request({"type":"http","method":"POST","path":"/","headers":[]})
            payload=MessageInput(telegram_user_id=user.telegram_user_id,text="Вес 80 кг",request_key="message-telegram-test",model=BotModel.FREE)
            result=await message(payload,request,db)
            assert seen["companion_context"]["channel"]=="telegram"
            assert "search_catalog_products" in {tool["name"] for tool in seen["function_tools"]}
            assert "get_my_basket" not in {tool["name"] for tool in seen["function_tools"]}
            reply=result["messages"][-1]
            assert reply["cards"][0]["state"]=="pending"
            assert "action_token" not in reply["cards"][0]
            repeat=await message(payload,request,db)
            assert repeat["messages"]==result["messages"]
            professor.send_message_v2.assert_awaited_once()
            card=CardInput(telegram_user_id=user.telegram_user_id,message_id=reply["message_id"],card_id=reply["cards"][0]["id"],kind="dialogue_confirm",request_key="confirm-telegram-test")
            await action(card,db)
            await action(card,db)
            entries=list((await db.execute(select(AICompanionEntry).where(AICompanionEntry.user_id==user.id))).scalars())
            assert len(entries)==1
            summary=await control(Control(telegram_user_id=user.telegram_user_id,kind="progress",request_key="report-telegram-test"),db)
            assert summary["text"]
            await control(Control(telegram_user_id=user.telegram_user_id,kind="eligibility",confirmed=True,request_key="eligible-telegram-test"),db)
            assert (await service.profile_for(db,user.id)).settings["nutrition_auto_eligible"]
            await control(Control(telegram_user_id=user.telegram_user_id,kind="stop",request_key="stop-telegram-test"),db)
            assert (await service.profile_for(db,user.id)).settings["checkin_time"] is None
            await control(Control(telegram_user_id=user.telegram_user_id,kind="erase",confirmed=True,request_key="erase-telegram-test"),db)
            assert await service.profile_for(db,user.id) is None
    asyncio.run(run())


def test_catalog_database_relations_discounts_and_stock():
    from decimal import Decimal
    from src.database.models import Product, Variant, ProductCategory, ProductByCategory, CatalogSettings
    from src.app.modules.telegram_ai.catalog import read_catalog, CatalogRequest
    async def run():
        async with database() as (db,user):
            category=ProductCategory(name="Mentor discount test",discount_percent=Decimal("20"))
            product=Product(sku="MENTOR-CATALOG-TEST",name="Mentor catalog test",in_stock=True,discount_percent=Decimal("5"))
            db.add_all([category,product]);await db.flush()
            variant=Variant(product_id=product.id,name="Package",price=Decimal("100"),stock=3)
            db.add_all([variant,ProductByCategory(product_id=product.id,category_id=category.id),CatalogSettings(id=1,stock_reduction_enabled=True,stock_reduction=5)])
            await db.flush()
            product_id,variant_id=product.id,variant.id
            db.expunge_all()  # Force real async relationship loading, as on a new API request.
            for name,args in [("search_catalog_products",{"query":"MENTOR-CATALOG-TEST"}),("get_catalog_product",{"product_id":product_id}),("get_product_stock",{"product_id":product_id}),("get_product_stock",{"variant_id":variant_id})]:
                result=await read_catalog(db,CatalogRequest(name=name,arguments=args))
                assert result["ok"]
                item=result["items"][0]["variants"][0] if "items" in result else result["product"]["variants"][0] if "product" in result else result["variants"][0] if "variants" in result else result["variant"]
                assert item["stock"]==0 and not item["in_stock"]
                assert item["price"]=="80.00"
    asyncio.run(run())
