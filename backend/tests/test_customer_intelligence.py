from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import uuid

import pytest
from pydantic import ValidationError
from sqlalchemy.dialects import postgresql

from src.app.modules.users.me.schemas.customer_intelligence import (
    CustomerEventPayload,
    CustomerIntelligenceSyncPayload,
    UserDeviceSyncPayload,
)
from src.app.services.admin.audiences import build_audience_query, normalize_segment_filters
from src.database import Base


def _event(**overrides):
    values = {
        "event_id": uuid.uuid4(),
        "name": "app_opened",
        "occurred_at": datetime.now(timezone.utc),
        "session_id": str(uuid.uuid4()),
        "properties": {},
    }
    values.update(overrides)
    return CustomerEventPayload.model_validate(values)


def test_customer_intelligence_sync_contract_accepts_device_and_events():
    payload = CustomerIntelligenceSyncPayload(
        device=UserDeviceSyncPayload(
            installation_id=str(uuid.uuid4()),
            platform="ios",
            app_version="1.2.3",
            app_build="42",
            os_version="18.5",
            language="ru-AM",
            timezone="Asia/Yerevan",
            push_permission="granted",
        ),
        events=[
            _event(),
            _event(
                name="product_viewed",
                entity_type="product",
                entity_id=123,
                properties={"variant_id": 456},
            ),
        ],
    )

    assert payload.device is not None
    assert payload.device.push_permission == "granted"
    assert [event.name for event in payload.events] == ["app_opened", "product_viewed"]


def test_customer_intelligence_sync_rejects_duplicate_event_ids():
    event_id = uuid.uuid4()
    with pytest.raises(ValidationError, match="Duplicate event_id"):
        CustomerIntelligenceSyncPayload(events=[
            _event(event_id=event_id),
            _event(event_id=event_id),
        ])


def test_customer_event_rejects_old_or_oversized_payloads():
    with pytest.raises(ValidationError, match="90-day"):
        _event(occurred_at=datetime.now(timezone.utc) - timedelta(days=91))

    with pytest.raises(ValidationError, match="8 KB"):
        _event(properties={"value": "x" * 9000})


def test_customer_intelligence_tables_are_registered():
    expected_tables = {
        "user_devices",
        "user_events",
        "customer_marketing_profiles",
        "customer_consents",
        "customer_attribution",
    }
    assert expected_tables.issubset(Base.metadata.tables)


@pytest.mark.parametrize(
    ("field", "operator", "value"),
    [
        ("platform", "eq", "ios"),
        ("app_version", "contains", "1.2"),
        ("push_permission", "eq", "granted"),
        ("install_source", "contains", "utm_source"),
        ("lifecycle_stage", "eq", "high_intent"),
        ("lead_score", "gte", 20),
        ("event_count", "gte", 3),
        ("event_name", "eq", "product_viewed"),
    ],
)
def test_customer_intelligence_segment_fields_compile(field, operator, value):
    filters = normalize_segment_filters({
        "version": 2,
        "combinator": "and",
        "conditions": [{"field": field, "operator": operator, "value": value}],
        "exclusions": [],
    })
    compiled = str(build_audience_query(filters).compile(
        dialect=postgresql.dialect(),
        compile_kwargs={"literal_binds": True},
    ))
    assert "users" in compiled


def test_customer_intelligence_sync_endpoint_is_idempotent(client, register_verified_user):
    auth = register_verified_user({
        "email": f"customer-intelligence-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Event",
        "surname": "Tester",
    })
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    event_id = str(uuid.uuid4())
    payload = {
        "device": {
            "installation_id": str(uuid.uuid4()),
            "platform": "ios",
            "app_version": "1.2.3",
            "app_build": "42",
            "os_version": "18.5",
            "device_model": "iPhone",
            "language": "ru-AM",
            "timezone": "Asia/Yerevan",
            "push_permission": "granted",
        },
        "consents": [{
            "purpose": "analytics",
            "channel": "all",
            "is_granted": True,
            "policy_version": "2026-07",
        }],
        "events": [{
            "event_id": event_id,
            "name": "app_opened",
            "occurred_at": datetime.now(timezone.utc).isoformat(),
            "session_id": str(uuid.uuid4()),
            "properties": {"trigger": "test"},
        }],
    }

    first = client.post("/api/v1/users/me/customer-intelligence/sync", json=payload, headers=headers)
    assert first.status_code == 200, first.text
    assert first.json()["accepted_events"] == 1
    assert first.json()["duplicate_events"] == 0
    assert first.json()["updated_consents"] == 1
    assert first.json()["device_id"] > 0

    second = client.post("/api/v1/users/me/customer-intelligence/sync", json=payload, headers=headers)
    assert second.status_code == 200, second.text
    assert second.json()["accepted_events"] == 0
    assert second.json()["duplicate_events"] == 1

    concurrent_payload = {
        **payload,
        "events": [{
            **payload["events"][0],
            "event_id": str(uuid.uuid4()),
            "occurred_at": datetime.now(timezone.utc).isoformat(),
        }],
    }
    with ThreadPoolExecutor(max_workers=2) as executor:
        responses = list(executor.map(
            lambda _: client.post(
                "/api/v1/users/me/customer-intelligence/sync",
                json=concurrent_payload,
                headers=headers,
            ),
            range(2),
        ))
    assert all(response.status_code == 200 for response in responses)
    assert sum(response.json()["accepted_events"] for response in responses) == 1
    assert sum(response.json()["duplicate_events"] for response in responses) == 1
