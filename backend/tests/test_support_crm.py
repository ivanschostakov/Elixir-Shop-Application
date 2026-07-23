from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import psycopg2
from psycopg2.extras import Json
import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from config import POSTGRES_DB, POSTGRES_HOST, POSTGRES_PASSWORD, POSTGRES_PORT, POSTGRES_USER
from src.app.main import app
from src.app.modules.admin.schemas import AdminLeadUpdatePayload
from src.app.services.admin.permissions import ALL_PERMISSIONS, AdminContext, get_current_admin_context
from src.database import Base


def _database_connection():
    return psycopg2.connect(
        dbname=POSTGRES_DB,
        user=POSTGRES_USER,
        password=POSTGRES_PASSWORD,
        host=POSTGRES_HOST,
        port=POSTGRES_PORT,
    )


def _promote_to_support_admin(*, user_id: int) -> None:
    with _database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO admins (user_id, is_active, mfa_confirmed_at, locale)
            VALUES (%s, true, now(), 'ru')
            ON CONFLICT (user_id) DO UPDATE
            SET is_active = true, mfa_confirmed_at = now()
            """,
            (user_id,),
        )
        cursor.execute(
            """
            INSERT INTO admin_role_assignments (admin_user_id, role_id, assigned_by_user_id)
            SELECT %s, id, %s
            FROM admin_roles
            WHERE code = 'support'
            ON CONFLICT (admin_user_id, role_id) DO NOTHING
            """,
            (user_id, user_id),
        )


def _seed_ai_chat(*, user_id: int) -> int:
    with _database_connection() as connection, connection.cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO chats (user_id, conversation_id, current_tokens, total_tokens)
            VALUES (%s, %s, 18, 42)
            RETURNING id
            """,
            (user_id, f"crm-test-{uuid.uuid4()}"),
        )
        chat_id = int(cursor.fetchone()[0])
        cursor.execute(
            """
            INSERT INTO ai_messages (user_id, chat_id, text, sender, context_json)
            VALUES
                (%s, %s, %s, 'user', %s),
                (%s, %s, %s, 'ai', %s)
            """,
            (
                user_id,
                chat_id,
                "Подберите пептид для восстановления",
                Json({}),
                user_id,
                chat_id,
                "Посмотрите эту рекомендацию",
                Json({
                    "interactive": {
                        "action_token": "must-not-leak-to-crm",
                        "actions": [{"kind": "open_product", "product_id": 17}],
                    }
                }),
            ),
        )
        cursor.execute(
            """
            INSERT INTO user_events (
                event_id,
                user_id,
                event_name,
                source,
                entity_type,
                entity_id,
                occurred_at,
                properties_json,
                attribution_json
            )
            SELECT
                %s,
                %s,
                'ai_action_clicked',
                'app',
                'ai_message',
                id,
                now(),
                %s,
                '{}'::jsonb
            FROM ai_messages
            WHERE chat_id = %s AND sender = 'ai'
            """,
            (
                str(uuid.uuid4()),
                user_id,
                Json({
                    "action_id": "open-product-17",
                    "action_type": "open_product",
                    "product_id": 17,
                    "action_token": "must-not-leak-to-crm",
                }),
                chat_id,
            ),
        )
    return chat_id


def test_support_crm_schema_routes_and_permissions_are_registered():
    assert {
        "crm_conversations",
        "crm_messages",
        "crm_message_attachments",
        "crm_assignment_history",
        "crm_leads",
        "crm_lead_stage_history",
        "crm_lead_notes",
    }.issubset(Base.metadata.tables)
    paths = {route.path for route in app.routes}
    assert {
        "/api/v1/users/me/support",
        "/api/v1/users/me/support/conversations",
        "/api/v1/admin/support/conversations",
        "/api/v1/admin/ai-chats",
        "/api/v1/admin/leads",
    }.issubset(paths)
    assert {
        "support.read",
        "support.reply",
        "support.assign",
        "ai_chats.read",
        "leads.read",
        "leads.manage",
    }.issubset(ALL_PERMISSIONS)


def test_lead_terminal_stage_contract_requires_business_context():
    now = datetime.now(timezone.utc)
    with pytest.raises(ValidationError, match="lost_reason"):
        AdminLeadUpdatePayload(expected_updated_at=now, status="lost")
    with pytest.raises(ValidationError, match="converted_order_id"):
        AdminLeadUpdatePayload(expected_updated_at=now, status="converted")


def test_support_to_crm_reply_lead_and_ai_visibility_flow(
    client: TestClient,
    register_verified_user,
):
    customer_auth = register_verified_user({
        "email": f"support-customer-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Ирина",
        "surname": "Клиент",
    })
    operator_auth = register_verified_user({
        "email": f"support-operator-{uuid.uuid4().hex[:10]}@example.com",
        "password": "SafePassword123!",
        "name": "Анна",
        "surname": "Оператор",
    })
    customer_id = int(customer_auth["user"]["id"])
    operator_id = int(operator_auth["user"]["id"])
    _promote_to_support_admin(user_id=operator_id)
    ai_chat_id = _seed_ai_chat(user_id=customer_id)

    context = AdminContext(
        user=SimpleNamespace(id=operator_id, name="Анна", surname="Оператор"),
        admin=SimpleNamespace(user_id=operator_id),
        session=SimpleNamespace(id=1),
        roles=("support",),
        permissions=frozenset({"*"}),
    )
    app.dependency_overrides[get_current_admin_context] = lambda: context
    customer_headers = {"Authorization": f"Bearer {customer_auth['access_token']}"}

    try:
        first_client_message_id = str(uuid.uuid4())
        create_payload = {
            "client_message_id": first_client_message_id,
            "subject": "Нужна консультация",
            "message": "Подскажите, какой курс выбрать?",
        }
        created = client.post(
            "/api/v1/users/me/support/conversations",
            json=create_payload,
            headers=customer_headers,
        )
        assert created.status_code == 201, created.text
        conversation = created.json()
        conversation_id = int(conversation["id"])
        assert conversation["messages"][0]["author_name"] == "Ирина Клиент"

        duplicate = client.post(
            "/api/v1/users/me/support/conversations",
            json=create_payload,
            headers=customer_headers,
        )
        assert duplicate.status_code == 201, duplicate.text
        assert duplicate.json()["id"] == conversation_id

        second = client.post(
            f"/api/v1/users/me/support/conversations/{conversation_id}/messages",
            data={
                "client_message_id": str(uuid.uuid4()),
                "message": "Можно начать с минимального набора?",
            },
            headers=customer_headers,
        )
        assert second.status_code == 200, second.text
        assert len(second.json()["messages"]) == 2

        queue = client.get(
            "/api/v1/admin/support/conversations",
            params={"status": "all", "customer_user_id": customer_id},
        )
        assert queue.status_code == 200, queue.text
        assert queue.json()["total"] == 1
        assert queue.json()["items"][0]["admin_unread_count"] == 2

        reply = client.post(
            f"/api/v1/admin/support/conversations/{conversation_id}/messages",
            json={"body": "Да, начнём с базового варианта.", "is_internal": False},
        )
        assert reply.status_code == 200, reply.text
        reply_body = reply.json()
        assert reply_body["status"] == "waiting_customer"
        assert reply_body["messages"][-1]["author_name"] == "Анна Оператор"
        assert reply_body["messages"][-1]["author_role"] == "Поддержка"

        internal_note = client.post(
            f"/api/v1/admin/support/conversations/{conversation_id}/messages",
            json={"body": "Высокий интерес — создать лид.", "is_internal": True},
        )
        assert internal_note.status_code == 200, internal_note.text
        assert internal_note.json()["messages"][-1]["is_internal"] is True

        customer_thread = client.get(
            f"/api/v1/users/me/support/conversations/{conversation_id}",
            headers=customer_headers,
        )
        assert customer_thread.status_code == 200, customer_thread.text
        visible_messages = customer_thread.json()["messages"]
        assert visible_messages[-1]["author_name"] == "Анна Оператор"
        assert all(not message["is_internal"] for message in visible_messages)

        marked_read = client.post(
            f"/api/v1/users/me/support/conversations/{conversation_id}/read",
            headers=customer_headers,
        )
        assert marked_read.status_code == 200, marked_read.text
        assert marked_read.json()["unread_count"] == 0

        created_lead = client.post(
            "/api/v1/admin/leads",
            json={
                "title": "Консультация по базовому курсу",
                "source": "support",
                "score": 75,
                "priority": "high",
                "conversation_id": conversation_id,
                "description": "Клиент готов обсуждать первый заказ.",
            },
        )
        assert created_lead.status_code == 201, created_lead.text
        lead = created_lead.json()
        lead_id = int(lead["id"])
        assert lead["customer_user_id"] == customer_id
        assert lead["owner_user_id"] == operator_id
        assert lead["stage_history"][0]["to_status"] == "new"

        lost = client.patch(
            f"/api/v1/admin/leads/{lead_id}",
            json={
                "expected_updated_at": lead["updated_at"],
                "status": "lost",
                "lost_reason": "Клиент отложил покупку",
                "stage_reason": "Вернуться через месяц",
            },
        )
        assert lost.status_code == 200, lost.text
        assert lost.json()["status"] == "lost"
        assert lost.json()["stage_history"][-1]["from_status"] == "new"

        active_leads = client.get(
            "/api/v1/admin/leads",
            params={"status": "active", "customer_user_id": customer_id},
        )
        all_leads = client.get(
            "/api/v1/admin/leads",
            params={"status": "all", "customer_user_id": customer_id},
        )
        assert active_leads.status_code == 200, active_leads.text
        assert active_leads.json()["total"] == 0
        assert all_leads.status_code == 200, all_leads.text
        assert all_leads.json()["total"] == 1

        ai_list = client.get(
            "/api/v1/admin/ai-chats",
            params={"user_id": customer_id},
        )
        assert ai_list.status_code == 200, ai_list.text
        assert ai_list.json()["items"][0]["id"] == ai_chat_id
        assert ai_list.json()["items"][0]["messages_count"] == 2

        ai_detail = client.get(f"/api/v1/admin/ai-chats/{ai_chat_id}")
        assert ai_detail.status_code == 200, ai_detail.text
        ai_context = ai_detail.json()["messages"][-1]["context"]
        assert ai_context["interactive"]["actions"][0]["kind"] == "open_product"
        assert "action_token" not in ai_context["interactive"]
        assert ai_detail.json()["actions"][0]["action_type"] == "open_product"
        assert ai_detail.json()["actions"][0]["product_id"] == 17
        assert "action_token" not in ai_detail.json()["actions"][0]["properties"]

        missing_ai_attachment = client.get("/api/v1/admin/ai-chats/attachments/999999999")
        assert missing_ai_attachment.status_code == 404, missing_ai_attachment.text
        assert missing_ai_attachment.json()["detail"] == "AI chat attachment not found"
    finally:
        app.dependency_overrides.pop(get_current_admin_context, None)
