from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import timedelta
from types import SimpleNamespace

import pytest

import src.app.services.notifications as notifications_service


@dataclass
class _FakeScalarResult:
    rows: list | None = None
    scalar_value: object | None = None

    def all(self):
        return self.rows or []

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
    subscription = SimpleNamespace(user_id=11, variant_id=33, is_active=True, notified_at=None)
    variant = SimpleNamespace(id=33, product_id=7, name="Test Variant", stock=5)

    session = _FakeSession(
        [
            _FakeScalarResult(rows=[(subscription, variant)]),
        ]
    )

    async def fake_send_push_to_user(*args, **kwargs):
        return True

    monkeypatch.setattr(notifications_service, "send_push_to_user", fake_send_push_to_user)

    sent_count = asyncio.run(notifications_service.process_restock_notifications(session, now=notifications_service.ufa_now()))

    assert sent_count == 1
    assert subscription.is_active is False
    assert subscription.notified_at is not None
    assert session.commits == 1
    assert len(session.added) == 1
    assert session.added[0].type == notifications_service.DISPATCH_TYPE_RESTOCK


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
