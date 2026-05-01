from __future__ import annotations

import asyncio
from types import SimpleNamespace

import src.app.services.push_notifications as push_notifications


def test_send_push_to_user_skips_when_user_is_already_on_redirect_path(monkeypatch):
    async def fake_get_user_push_tokens(_session, *, user_id: int):
        assert user_id == 42
        return [SimpleNamespace(expo_push_token="ExponentPushToken[same-path]", current_path="/chat")]

    send_calls: list[list[dict]] = []

    async def fake_send_expo_push_messages(messages):
        send_calls.append(messages)
        return set()

    async def fake_delete_invalid_push_tokens(*_args, **_kwargs):
        return None

    monkeypatch.setattr(push_notifications, "get_user_push_tokens", fake_get_user_push_tokens)
    monkeypatch.setattr(push_notifications, "_send_expo_push_messages", fake_send_expo_push_messages)
    monkeypatch.setattr(push_notifications, "_delete_invalid_push_tokens", fake_delete_invalid_push_tokens)

    sent = asyncio.run(
        push_notifications.send_push_to_user(
            session=SimpleNamespace(),
            user_id=42,
            title="New AI reply",
            body="We prepared your answer.",
            data={"type": "ai_reply"},
        )
    )

    assert sent is False
    assert send_calls == []


def test_send_push_to_user_sends_when_user_is_on_different_path(monkeypatch):
    async def fake_get_user_push_tokens(_session, *, user_id: int):
        assert user_id == 42
        return [SimpleNamespace(expo_push_token="ExponentPushToken[other-path]", current_path="/discover")]

    send_calls: list[list[dict]] = []

    async def fake_send_expo_push_messages(messages):
        send_calls.append(messages)
        return set()

    async def fake_delete_invalid_push_tokens(*_args, **_kwargs):
        return None

    monkeypatch.setattr(push_notifications, "get_user_push_tokens", fake_get_user_push_tokens)
    monkeypatch.setattr(push_notifications, "_send_expo_push_messages", fake_send_expo_push_messages)
    monkeypatch.setattr(push_notifications, "_delete_invalid_push_tokens", fake_delete_invalid_push_tokens)

    sent = asyncio.run(
        push_notifications.send_push_to_user(
            session=SimpleNamespace(),
            user_id=42,
            title="New AI reply",
            body="We prepared your answer.",
            data={"type": "ai_reply"},
        )
    )

    assert sent is True
    assert len(send_calls) == 1
    assert send_calls[0][0]["to"] == "ExponentPushToken[other-path]"
