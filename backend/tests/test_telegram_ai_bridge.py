import asyncio
import time
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from starlette.requests import Request

from src.app.modules.telegram_ai import auth
from src.app.modules.telegram_ai.catalog import CatalogRequest, CATALOG_NAMES, CATALOG_TOOLS
from src.app.modules.telegram_ai.router import public_message, action, CardInput, Start


def request(body=b'{}', **overrides):
    stamp, nonce, path = str(int(time.time())), "a" * 32, "/api/v1/integrations/telegram-ai/catalog"
    key = "test-key-" * 8
    headers = {"x-elixir-timestamp": stamp, "x-elixir-nonce": nonce,
               "x-elixir-signature": auth.signature(key, stamp, nonce, "POST", path, body)}
    headers.update(overrides)
    async def receive(): return {"type":"http.request","body":body,"more_body":False}
    return Request({"type":"http","method":"POST","path":path,"headers":[(k.encode(),v.encode()) for k,v in headers.items()]}, receive), key


def test_signed_request_and_replay(monkeypatch):
    req,key=request()
    monkeypatch.setattr(auth.config,"TELEGRAM_AI_BRIDGE_ENABLED",True)
    monkeypatch.setattr(auth.config,"TELEGRAM_AI_BRIDGE_SECRET",key)
    cache=SimpleNamespace(set=AsyncMock(side_effect=[True,False]))
    monkeypatch.setattr(auth,"get_cache_service",lambda:SimpleNamespace(client=cache))
    asyncio.run(auth.require_bot(req))
    with pytest.raises(HTTPException) as error: asyncio.run(auth.require_bot(req))
    assert error.value.status_code==401


@pytest.mark.parametrize("header,value",[("x-elixir-signature","bad"),("x-elixir-timestamp","0"),("x-elixir-nonce","bad")])
def test_reject_invalid_auth(monkeypatch,header,value):
    req,key=request(**{header:value})
    monkeypatch.setattr(auth.config,"TELEGRAM_AI_BRIDGE_ENABLED",True)
    monkeypatch.setattr(auth.config,"TELEGRAM_AI_BRIDGE_SECRET",key)
    with pytest.raises(HTTPException) as error: asyncio.run(auth.require_bot(req))
    assert error.value.status_code==401


def test_signature_binds_body_path_and_method():
    args=("secret","100","abc","POST","/catalog",b'{}')
    original=auth.signature(*args)
    for index, value in ((3,"GET"),(4,"/mentor/actions"),(5,b'{"telegram_user_id":2}')):
        changed=list(args);changed[index]=value
        assert auth.signature(*changed)!=original


def test_catalog_cannot_access_customer_tools():
    assert {t["name"] for t in CATALOG_TOOLS}==CATALOG_NAMES
    with pytest.raises(ValidationError): CatalogRequest(name="get_my_basket")
    with pytest.raises(ValidationError): CatalogRequest(name="get_catalog_product",telegram_user_id=1)


def test_public_cards_exclude_private_undo_and_signatures():
    message=SimpleNamespace(id=3,text="Проверьте",context_json={"dialogue_cards":[{"id":"dialogue_0","kind":"entry","state":"pending","summary":"Вес","operation":{"kind":"entry"},"action_token":"secret","undo":{"old":"health"},"guard":"private"}]})
    result=public_message(message)
    assert result["cards"][0]["operation"]=={"kind":"entry"}
    assert not {"action_token","undo","guard"} & result["cards"][0].keys()


def test_card_owner_is_checked_before_action(monkeypatch):
    from src.app.modules.telegram_ai import router as module
    # Package exports router module under its normal import path.
    import importlib
    module=importlib.import_module("src.app.modules.telegram_ai.router")
    monkeypatch.setattr(module,"owned_user",AsyncMock(return_value=SimpleNamespace(id=1)))
    monkeypatch.setattr(module,"active_profile",AsyncMock())
    db=SimpleNamespace(get=AsyncMock(return_value=SimpleNamespace(user_id=2)))
    with pytest.raises(HTTPException) as error:
        asyncio.run(action(CardInput(telegram_user_id=11,message_id=3,card_id="dialogue_0",kind="dialogue_confirm",request_key="request-123"),db))
    assert error.value.status_code==404


def test_start_requires_explicit_adult_field():
    with pytest.raises(ValidationError): Start(telegram_user_id=1,request_key="start-123")


def test_catalog_uses_public_stock_and_catalog_discount():
    from decimal import Decimal
    from src.app.modules.telegram_ai.catalog import apply_visibility
    from src.app.services.stock_visibility import StockVisibilityPolicy
    product=SimpleNamespace(id=1,stock_reduction_override=5,discount_percent=Decimal("10"))
    result={"items":[{"product_id":1,"in_stock":True,"variants":[{"product_id":1,"stock":3,"in_stock":True,"price":"100.00"}]}]}
    apply_visibility(result,{1:product},StockVisibilityPolicy(enabled=True,global_reduction=1))
    variant=result["items"][0]["variants"][0]
    assert variant["stock"]==0 and not variant["in_stock"]
    assert not result["items"][0]["in_stock"]
    assert variant["price"]=="90.00" and variant["original_price"]=="100.00"
