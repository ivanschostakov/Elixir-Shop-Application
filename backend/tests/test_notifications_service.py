import asyncio
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

import pytest

import src.app.services.notifications.core as notifications_service


@dataclass
class _FakeScalarResult:
    rows: list | None = None
    scalar_value: object | None = None

    def all(self):
        return self.rows or []

    def scalars(self):
        return self

    def scalar_one(self):
        return self.scalar_value

    def scalar_one_or_none(self):
        return self.scalar_value


class _FakeSession:
    def __init__(self, responses: list[_FakeScalarResult]):
        self._responses = responses
        self.added: list[object] = []
        self.commits = 0
        self.rollbacks = 0
        self.flushes = 0

    async def execute(self, _stmt):
        assert self._responses, "No fake DB response queued"
        return self._responses.pop(0)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        self.flushes += 1

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        self.rollbacks += 1


def test_restock_processor_sends_once_and_deactivates(monkeypatch: pytest.MonkeyPatch):
    subscription = SimpleNamespace(user_id=11, variant_id=33, is_active=True, last_seen_stock=0, notified_at=None)
    variant = SimpleNamespace(id=33, product_id=7, name="Test Variant", stock=5)
    captured_payload: dict[str, object] = {}

    session = _FakeSession(
        [
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(rows=[(subscription, variant)]),
            _FakeScalarResult(rows=[]),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        captured_payload.update(kwargs)
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    sent_count = asyncio.run(notifications_service.process_restock_notifications(session, now=notifications_service.ufa_now()))

    assert sent_count == 1
    assert subscription.is_active is False
    assert subscription.last_seen_stock == 5
    assert subscription.notified_at is not None
    assert session.commits == 1
    assert len(session.added) == 1
    assert session.added[0].type == notifications_service.DISPATCH_TYPE_RESTOCK
    assert captured_payload["title"] == "Товар снова в наличии"
    assert captured_payload["body"] == "Вариант Test Variant снова в наличии."
    assert captured_payload["data"] == {
        "type": "restock",
        "variant_id": 33,
        "variant_name": "Test Variant",
        "product_id": 7,
    }


def test_restock_processor_waits_for_stock_increase(monkeypatch: pytest.MonkeyPatch):
    subscription = SimpleNamespace(user_id=11, variant_id=33, is_active=True, last_seen_stock=5, notified_at=None)
    variant = SimpleNamespace(id=33, product_id=7, name="Test Variant", stock=5)

    session = _FakeSession(
        [
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(rows=[]),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        pytest.fail("Restock notification should wait until stock increases")

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    sent_count = asyncio.run(notifications_service.process_restock_notifications(session, now=notifications_service.ufa_now()))

    assert sent_count == 0
    assert subscription.is_active is True
    assert subscription.last_seen_stock == 5
    assert session.commits == 1
    assert session.added == []


def test_restock_processor_tracks_low_stock_decreases(monkeypatch: pytest.MonkeyPatch):
    subscription = SimpleNamespace(user_id=11, variant_id=33, is_active=True, last_seen_stock=5, notified_at=None)
    variant = SimpleNamespace(id=33, product_id=7, name="Test Variant", stock=2)

    session = _FakeSession(
        [
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(rows=[]),
            _FakeScalarResult(rows=[(subscription, variant)]),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        pytest.fail("Lower stock should update the baseline without sending")

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    sent_count = asyncio.run(notifications_service.process_restock_notifications(session, now=notifications_service.ufa_now()))

    assert sent_count == 0
    assert subscription.is_active is True
    assert subscription.last_seen_stock == 2
    assert session.commits == 1
    assert session.added == []


def test_inactive_customer_processor_respects_cooldown(monkeypatch: pytest.MonkeyPatch):
    now = notifications_service.ufa_now()

    first_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(77, now - timedelta(days=60))]),
            _FakeScalarResult(scalar_value=None),
        ]
    )
    second_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(77, now - timedelta(days=60))]),
            _FakeScalarResult(scalar_value=now),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    first_sent = asyncio.run(notifications_service.process_inactive_customer_notifications(first_session, now=now))
    second_sent = asyncio.run(notifications_service.process_inactive_customer_notifications(second_session, now=now))

    assert first_sent == 1
    assert second_sent == 0
    assert len(first_session.added) == 1
    assert first_session.added[0].type == notifications_service.DISPATCH_TYPE_INACTIVE_CUSTOMER


def test_abandoned_cart_processor_respects_cooldown(monkeypatch: pytest.MonkeyPatch):
    now = notifications_service.ufa_now()
    basket_updated_at = now - timedelta(hours=30)

    first_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(88, basket_updated_at)]),
            _FakeScalarResult(scalar_value=None),
            _FakeScalarResult(scalar_value=None),
        ]
    )
    second_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(88, basket_updated_at)]),
            _FakeScalarResult(scalar_value=None),
            _FakeScalarResult(scalar_value=now),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    first_sent = asyncio.run(notifications_service.process_abandoned_cart_notifications(first_session, now=now))
    second_sent = asyncio.run(notifications_service.process_abandoned_cart_notifications(second_session, now=now))

    assert first_sent == 1
    assert second_sent == 0
    assert len(first_session.added) == 1
    assert first_session.added[0].type == notifications_service.DISPATCH_TYPE_ABANDONED_CART


def test_review_reminder_processor_sends_once_per_product(monkeypatch: pytest.MonkeyPatch):
    now = notifications_service.ufa_now()

    send_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(91, 501, now - timedelta(days=40))]),
            _FakeScalarResult(scalar_value=None),
            _FakeScalarResult(scalar_value=None),
        ]
    )
    skip_session = _FakeSession(
        [
            _FakeScalarResult(rows=[(91, 501, now - timedelta(days=40))]),
            _FakeScalarResult(scalar_value=999),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    sent = asyncio.run(notifications_service.process_review_reminders(send_session, now=now))
    skipped = asyncio.run(notifications_service.process_review_reminders(skip_session, now=now))

    assert sent == 1
    assert skipped == 0
    assert len(send_session.added) == 1
    assert send_session.added[0].type == notifications_service.DISPATCH_TYPE_REVIEW_REMINDER


def test_community_message_processor_excludes_sender(monkeypatch: pytest.MonkeyPatch):
    now = notifications_service.ufa_now()
    message = SimpleNamespace(
        id=501,
        app_user_id=11,
        topic_id=23,
        deleted_at=None,
        text="  New   community message  ",
        attachments=[],
        author=SimpleNamespace(full_name="Татьяна"),
        topic=SimpleNamespace(name="Приложение"),
    )
    event = SimpleNamespace(
        message=message,
        attempts=0,
        next_attempt_at=None,
        sent_at=None,
        last_error=None,
    )
    session = _FakeSession([
        _FakeScalarResult(rows=[event]),
        _FakeScalarResult(rows=[11, 12, 13]),
    ])
    captured: dict[str, object] = {}

    async def fake_send_push_to_users(*args, **kwargs):
        captured.update(kwargs)
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_users", fake_send_push_to_users)

    processed = asyncio.run(notifications_service.process_community_message_notifications(session, now=now))

    assert processed == 1
    assert captured["user_ids"] == [12, 13]
    assert captured["title"] == "Приложение"
    assert captured["body"] == "Татьяна: New community message"
    assert captured["data"] == {"type": "community_message", "topic_id": 23, "message_id": 501}
    assert captured["channel_id"] == "community_messages"
    assert event.sent_at == now
    assert event.last_error is None
    assert session.commits == 1


def test_community_message_processor_retries_failed_delivery(monkeypatch: pytest.MonkeyPatch):
    now = notifications_service.ufa_now()
    message = SimpleNamespace(
        id=502,
        app_user_id=None,
        topic_id=24,
        deleted_at=None,
        text="",
        attachments=[SimpleNamespace(id=1)],
        author=SimpleNamespace(full_name="Участник"),
        topic=SimpleNamespace(name="Новости"),
    )
    event = SimpleNamespace(
        message=message,
        attempts=0,
        next_attempt_at=None,
        sent_at=None,
        last_error=None,
    )
    session = _FakeSession([
        _FakeScalarResult(rows=[event]),
        _FakeScalarResult(rows=[12]),
    ])

    async def fake_send_push_to_users(*args, **kwargs):
        raise RuntimeError("temporary push outage")

    monkeypatch.setattr(notifications_service, "send_push_to_users", fake_send_push_to_users)

    processed = asyncio.run(notifications_service.process_community_message_notifications(session, now=now))

    assert processed == 0
    assert event.sent_at is None
    assert event.attempts == 1
    assert event.last_error == "temporary push outage"
    assert event.next_attempt_at == now + timedelta(seconds=5)
    assert session.commits == 1
