import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError
from sqlalchemy import select

import config
from src.app.services.ai.companion import service
from src.app.services.ai.companion.dialogue_tools import DIALOGUE_TOOLS, execute_dialogue_tool
from src.app.services.ai.companion.photos import ProgressPhotosRead, serialize_entries
from src.app.services.ai.companion.schemas import Action, EntryData, MeasurementData, Settings, WorkoutData
from src.database.models import AIChat, AIMessage, Attachment, User
from src.database.models.ai.companion import AICompanionEntry, AIProviderResource
from src.integrations.ai.enums import AttachmentType, MessageSender
from test_ai_companion_db import URL, act, database, enable

db_test = pytest.mark.skipif(not URL, reason="Needs isolated companion_test DB")
NOW = datetime(2030, 1, 7, 12, tzinfo=timezone.utc)


@pytest.fixture(autouse=True)
def enabled(monkeypatch, tmp_path):
    import src.database.models.ai.attachment as attachment_model
    monkeypatch.setattr(config, "AI_COMPANION_ENABLED", True)
    monkeypatch.setattr(config, "AI_COMPANION_DIALOGUE_ENABLED", True)
    monkeypatch.setattr(service, "now_utc", lambda: NOW)
    monkeypatch.setattr(attachment_model, "PRIVATE_MEDIA_DIR", tmp_path)
    monkeypatch.setattr(attachment_model, "ATTACHMENTS_DIR", tmp_path / "public")


async def photo(db, user, *, private=True, sender=MessageSender.USER, kind=AttachmentType.IMAGE, mime="image/jpeg", file_exists=True):
    chat = (await db.execute(select(AIChat).where(AIChat.user_id == user.id))).scalar_one_or_none()
    if chat is None:
        chat = AIChat(user_id=user.id, conversation_id=f"photo:{uuid4()}")
        db.add(chat)
        await db.flush()
    message = AIMessage(user_id=user.id, chat_id=chat.id, sender=sender, text="Photo", is_sensitive=private)
    db.add(message)
    await db.flush()
    attachment = Attachment(message_id=message.id, is_private=private, type=kind, original_filename="progress.jpg", mime_type=mime, size_bytes=4)
    db.add(attachment)
    await db.flush()
    if file_exists:
        attachment.path.parent.mkdir(parents=True, exist_ok=True)
        attachment.path.write_bytes(b"test")
    await db.commit()
    return attachment


def test_photo_schema_forbids_urls_duplicates_and_inferred_metrics():
    valid = {"kind": "progress_photo", "occurred_at": NOW, "photo_attachment_ids": [1, 2]}
    assert EntryData.model_validate(valid).photo_attachment_ids == [1, 2]
    for patch in ({"photo_attachment_ids": []}, {"photo_attachment_ids": [1, 1]}, {"photo_attachment_ids": [0]},
                  {"photo_attachment_ids": list(range(1, 10))}, {"photo_attachment_ids": ["https://example.com/photo.jpg"]},
                  {"weight_kg": 70}, {"estimated": True}, {"kind": "meal", "name": "Not food"},
                  {"photo_url": "https://example.com/photo.jpg"}):
        with pytest.raises(ValidationError):
            EntryData.model_validate({**valid, **patch})
    schema = next(tool for tool in DIALOGUE_TOOLS if tool["name"] == "find_companion_records")
    assert {"workout", "measurement", "progress_photo"} <= set(schema["parameters"]["properties"]["kind"]["enum"])


@db_test
def test_photo_record_retries_versions_private_reads_and_non_metric_summary():
    async def run():
        async with database() as (db, user):
            profile = await enable(db, user)
            await act(db, user, "settings", expected_version=profile.version, settings=Settings(timezone="UTC"))
            attachment = await photo(db, user)
            payload = Action(kind="entry", request_key="photo-once-key", entry=EntryData(kind="progress_photo", occurred_at=NOW, photo_attachment_ids=[attachment.id], note="Front view"))
            first = await service.apply_action(db, user.id, payload)
            await db.commit()
            assert await service.apply_action(db, user.id, payload) == first
            rows = await service.entries_for(db, user.id, NOW - timedelta(days=1), NOW + timedelta(days=1), "progress_photo")
            assert len(rows) == 1
            record = rows[0]
            read = await serialize_entries(db, user.id, rows)
            parsed = ProgressPhotosRead(entries=read)
            image = parsed.entries[0].photo_attachments[0]
            assert image.is_private and image.id == attachment.id
            assert image.download_path == f"/api/v1/users/me/ai-chat/attachments/{attachment.id}"
            assert not parsed.entries[0].unavailable_photo_attachment_ids
            assert (await service.get_state(db, user.id))["entries"][0]["photo_attachments"][0]["id"] == attachment.id
            result = await execute_dialogue_tool(db, user.id, "find_companion_records", {"kind": "progress_photo", "from_date": NOW.date().isoformat(), "to_date": (NOW + timedelta(days=1)).date().isoformat(), "query": "Front"}, False)
            assert result["ok"] and result["data"]["entries"][0]["id"] == record.id
            summary = await service.summary_for(db, user.id, NOW - timedelta(days=7), NOW + timedelta(days=1))
            assert summary["meals_logged"] == summary["weight_measurements"] == summary["measurements"]["count"] == summary["workouts"]["sessions"] == 0
            changed = payload.entry.model_copy(update={"note": "Updated note"})
            await act(db, user, "entry", resource_id=record.id, expected_version=1, entry=changed)
            with pytest.raises(HTTPException) as error:
                await act(db, user, "entry", resource_id=record.id, expected_version=1, entry=changed)
            assert error.value.status_code == 409
            await act(db, user, "delete_entry", resource_id=record.id, expected_version=record.version)
            assert attachment.path.is_file()  # Removing the album record keeps its chat source.
            assert not await service.entries_for(db, user.id, NOW - timedelta(days=1), NOW + timedelta(days=1), "progress_photo")
    asyncio.run(run())


@db_test
def test_photos_reject_foreign_public_generated_missing_and_documents():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            foreign = User(name="Other", surname="Photo", password_hash="unused")
            db.add(foreign)
            await db.flush()
            await enable(db, foreign)
            invalid = [await photo(db, foreign), await photo(db, user, private=False), await photo(db, user, sender=MessageSender.AI),
                await photo(db, user, kind=AttachmentType.DOCUMENT, mime="application/pdf"),
                await photo(db, user, mime="image/svg+xml"), await photo(db, user, file_exists=False)]
            for attachment in invalid:
                with pytest.raises(HTTPException) as error:
                    await act(db, user, "entry", entry=EntryData(kind="progress_photo", occurred_at=NOW, photo_attachment_ids=[attachment.id]))
                assert error.value.status_code == 422
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            own = await photo(db, user)
            await act(db, user, "entry", entry=EntryData(kind="progress_photo", occurred_at=NOW, photo_attachment_ids=[own.id]))
            record = (await db.execute(select(AICompanionEntry))).scalar_one()
            assert await serialize_entries(db, foreign.id, [record]) == []
            with pytest.raises(HTTPException) as error:
                await act(db, foreign, "delete_entry", resource_id=record.id, expected_version=record.version)
            assert error.value.status_code == 404
            # The reference survives unavailable media without serving another source.
            own.is_private = False
            await db.flush()
            read = (await serialize_entries(db, user.id, [record]))[0]
            assert not read["photo_attachments"] and read["unavailable_photo_attachment_ids"] == [own.id]
            own.is_private = True
            await db.flush()
            await service.revoke_consent(db, user.id)
            await db.commit()
            with pytest.raises(HTTPException) as error:
                await act(db, user, "entry", entry=EntryData(kind="progress_photo", occurred_at=NOW, photo_attachment_ids=[own.id]))
            assert error.value.status_code == 409
            await service.erase_companion(db, user.id)
            await db.commit()
            assert not list((await db.execute(select(AICompanionEntry))).scalars())
            assert any(r.kind == "local_file" and r.status == "pending_delete" for r in (await db.execute(select(AIProviderResource))).scalars())
    asyncio.run(run())


@db_test
def test_find_new_records_respects_kind_and_user():
    async def run():
        async with database() as (db, user):
            await enable(db, user)
            entries = [EntryData(kind="measurement", occurred_at=NOW, measurement=MeasurementData(waist_cm=80)),
                EntryData(kind="workout", occurred_at=NOW, workout=WorkoutData(name="Workout", exercises=[{"key": "a", "name": "Press", "sets": [{}]}]))]
            for entry in entries:
                await act(db, user, "entry", entry=entry)
                result = await execute_dialogue_tool(db, user.id, "find_companion_records", {"kind": entry.kind, "from_date": NOW.date().isoformat(), "to_date": (NOW + timedelta(days=1)).date().isoformat(), "query": ""}, False)
                assert result["ok"] and len(result["data"]["entries"]) == 1
                assert result["data"]["entries"][0]["kind"] == entry.kind
    asyncio.run(run())
