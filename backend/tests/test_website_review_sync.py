import asyncio
import hashlib
import hmac
import json
from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import UUID

import httpx
import pytest

from src.app.services import review_attachments
from src.database.models import Review, ReviewAttachment, ReviewModerationEvent
from src.integrations.website_reviews import (
    WebsiteReviewSyncStats,
    attachments,
    client as review_client,
    push,
    sync,
    sync_reviews_with_website,
    utils,
)
from src.integrations.website_reviews.attachments import _valid_website_attachment_url
from src.integrations.website_reviews.push import _push_rows
from src.integrations.website_reviews.utils import (
    _local_review_for_remote,
    _mark_review_synced,
    _push_payload,
    _remote_values,
    _review_state,
)


def test_remote_review_values_map_published_and_rejected_states():
    published = _remote_values({
        "rating": 5,
        "text": " Отлично ",
        "answer": " Спасибо ",
        "likes": 2,
        "dislikes": -1,
        "status": "published",
        "author_name": " Анна ",
        "author_email": "a@example.com",
        "updated_at": "2026-07-27T10:00:00+00:00",
    })
    assert published["value"] == 5
    assert published["text"] == "Отлично"
    assert published["moderated"] is True
    assert published["moderated_at"] == datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    assert published["rejected_at"] is None
    assert published["dislikes"] == 0

    rejected = _remote_values({
        "rating": 3,
        "status": "rejected",
        "updated_at": "2026-07-27T10:00:00+00:00",
    })
    assert rejected["moderated"] is False
    assert rejected["moderated_at"] == datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)
    assert rejected["rejected_at"] == datetime(2026, 7, 27, 10, 0, tzinfo=timezone.utc)

    pending = _remote_values({
        "rating": 4,
        "status": "pending",
        "updated_at": "2026-07-27T10:00:00+00:00",
    })
    assert pending["moderated"] is False
    assert pending["moderated_at"] is None
    assert pending["rejected_at"] is None


def test_local_review_state_is_stable():
    assert _review_state(SimpleNamespace(rejected_at=None, moderated=False)) == "pending"
    assert _review_state(SimpleNamespace(rejected_at=None, moderated=True)) == "published"
    assert _review_state(SimpleNamespace(rejected_at=datetime.now(timezone.utc), moderated=False)) == "rejected"


def test_mark_review_synced_keeps_local_and_remote_checkpoints_equal():
    review = SimpleNamespace(
        website_review_id=None,
        website_updated_at=None,
        updated_at=datetime(2026, 7, 29, 9, 0, tzinfo=timezone.utc),
    )
    _mark_review_synced(review, {
        "remote_id": 105,
        "updated_at": "2026-07-29T10:00:00+00:00",
    })
    expected = datetime(2026, 7, 29, 10, 0, tzinfo=timezone.utc)
    assert review.website_review_id == 105
    assert review.website_updated_at == expected
    assert review.updated_at == expected


def test_pull_links_remote_review_back_to_its_app_review():
    review = SimpleNamespace(
        id=213,
        product_id=255,
        website_review_id=None,
    )
    existing_by_remote_id = {}
    matched = _local_review_for_remote(
        {
            "remote_id": 111,
            "app_review_id": 213,
        },
        product_id=255,
        existing_by_remote_id=existing_by_remote_id,
        existing_by_app_id={213: review},
    )
    assert matched is review
    assert review.website_review_id == 111
    assert existing_by_remote_id[111] is review


def test_pull_does_not_link_app_review_from_another_product():
    review = SimpleNamespace(
        id=213,
        product_id=255,
        website_review_id=None,
    )
    matched = _local_review_for_remote(
        {
            "remote_id": 111,
            "app_review_id": 213,
        },
        product_id=999,
        existing_by_remote_id={},
        existing_by_app_id={213: review},
    )
    assert matched is None
    assert review.website_review_id is None


def test_push_payload_contains_public_attachment_urls(monkeypatch):
    monkeypatch.setattr(
        utils,
        "PUBLIC_API_BASE_URL",
        "https://api.example.test",
    )
    now = datetime(2026, 7, 29, tzinfo=timezone.utc)
    review = SimpleNamespace(
        id=42,
        website_review_id=None,
        value=5,
        text="Отлично",
        answer=None,
        likes=0,
        dislikes=0,
        rejected_at=None,
        moderated=False,
        guest_name="Анна",
        guest_email="anna@example.test",
        attachments=[
            SimpleNamespace(
                id=7,
                website_file_id=812,
                filename="photo.jpg",
                mime_type="image/jpeg",
            ),
        ],
        created_at=now,
        updated_at=now,
    )
    payload = _push_payload(
        review,
        system_id="2ea8f4e1-3558-4899-aa99-0de6fc617496",
        email=None,
        name=None,
        surname=None,
    )
    assert payload["status"] == "pending"
    assert payload["attachments"] == [{
        "app_attachment_id": 7,
        "website_file_id": 812,
        "url": "https://api.example.test/media/reviews/42/photo.jpg",
        "filename": "photo.jpg",
        "mime_type": "image/jpeg",
    }]


def test_website_attachment_url_is_restricted_to_sotbit_uploads(monkeypatch):
    monkeypatch.setattr(
        attachments,
        "WEBSITE_REVIEW_SYNC_ENDPOINT",
        "https://elixirpeptide.com:8443/bitrix/tools/elixir.reviewsync/sync.php",
    )
    assert _valid_website_attachment_url(
        "https://elixirpeptide.com/upload/sotbit.reviews/a63/photo.jpg",
    )
    assert not _valid_website_attachment_url(
        "https://other.example/upload/sotbit.reviews/a63/photo.jpg",
    )
    assert not _valid_website_attachment_url(
        "https://elixirpeptide.com/private/secret.txt",
    )


def test_push_rows_keeps_missing_product_review_pending():
    async def run() -> None:
        now = datetime(2026, 7, 30, tzinfo=timezone.utc)
        review = SimpleNamespace(
            id=213,
            website_review_id=None,
            website_updated_at=None,
            value=5,
            text="Отлично",
            answer=None,
            likes=0,
            dislikes=0,
            rejected_at=None,
            moderated=False,
            guest_name="Покупатель",
            guest_email=None,
            hide_sender_name=False,
            attachments=[],
            created_at=now,
            updated_at=now,
        )

        class FakeClient:
            async def request(self, action, payload):
                assert action == "push"
                assert payload["reviews"][0]["app_review_id"] == 213
                return {
                    "results": [{
                        "app_review_id": 213,
                        "remote_id": 0,
                        "outcome": "skipped_missing_product",
                        "updated_at": None,
                    }],
                }

        class FakeSession:
            async def flush(self):
                return None

        stats = WebsiteReviewSyncStats()
        await _push_rows(
            FakeSession(),
            FakeClient(),
            stats,
            [(review, "045dca71-8762-11f1-0a80-1062000ffb86", None, None, None)],
        )

        assert stats.skipped_missing_product == 1
        assert stats.pushed == 0
        assert review.website_review_id is None
        assert review.website_updated_at is None

    asyncio.run(run())


@pytest.mark.parametrize("value", ["2026-07-29T10:00:00", "2026-07-29T10:00:00Z"])
def test_remote_timestamps_keep_utc_when_no_offset_is_supplied(value):
    assert utils._parse_datetime(value) == datetime(2026, 7, 29, 10, tzinfo=timezone.utc)


@pytest.mark.parametrize("value", [None, "", "invalid", 123])
def test_invalid_remote_timestamps_are_ignored(value):
    assert utils._parse_datetime(value) is None


@pytest.mark.parametrize("response_body, error", [
    ({"ok": True, "reviews": []}, None),
    ({"ok": False, "error": "Sync rejected"}, "Sync rejected"),
    ([], "Invalid review sync response"),
])
def test_review_client_signs_requests_and_validates_responses(monkeypatch, response_body, error):
    monkeypatch.setattr(review_client, "WEBSITE_REVIEW_SYNC_ENDPOINT", "https://website.test/sync")
    monkeypatch.setattr(review_client, "WEBSITE_REVIEW_SYNC_SECRET", "test-secret")
    monkeypatch.setattr(review_client, "time", SimpleNamespace(time=lambda: 1234567890))
    requests = []

    def handle(request):
        requests.append(request)
        assert request.url == "https://website.test/sync"
        assert json.loads(request.content) == {"action": "push", "reviews": [{"text": "Отлично"}]}
        assert request.headers["X-Elixir-Timestamp"] == "1234567890"
        expected = hmac.new(b"test-secret", b"1234567890." + request.content, hashlib.sha256).hexdigest()
        assert request.headers["X-Elixir-Signature"] == expected
        return httpx.Response(200, json=response_body)

    async_client = httpx.AsyncClient
    monkeypatch.setattr(
        review_client.httpx,
        "AsyncClient",
        lambda **kwargs: async_client(transport=httpx.MockTransport(handle), **kwargs),
    )
    request = review_client.WebsiteReviewSyncClient().request("push", {"reviews": [{"text": "Отлично"}]})
    if error:
        with pytest.raises(RuntimeError, match=error):
            asyncio.run(request)
    else:
        assert asyncio.run(request) == response_body
    assert len(requests) == 1


def _query_result(rows):
    result = Mock()
    result.scalars.return_value.all.return_value = rows
    result.all.return_value = rows
    return result


def _app_review(**overrides):
    values = {
        "id": 213,
        "product_id": 255,
        "value": 5,
        "text": "Local edit",
        "answer": None,
        "likes": 0,
        "dislikes": 0,
        "moderated": False,
        "moderated_at": None,
        "rejected_at": None,
        "guest_name": "Анна",
        "guest_email": None,
        "website_review_id": None,
        "website_updated_at": datetime(2026, 7, 29, 8, tzinfo=timezone.utc),
        "created_at": datetime(2026, 7, 29, 8, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 7, 29, 10, tzinfo=timezone.utc),
        "attachments": [],
    }
    return Review(**(values | overrides))


def test_sync_resolves_variants_preserves_local_edits_and_applies_website_moderation(monkeypatch):
    product_key = UUID("2ea8f4e1-3558-4899-aa99-0de6fc617496")
    variant_key = UUID("045dca71-8762-11f1-0a80-1062000ffb86")
    product = SimpleNamespace(id=255, system_id=product_key)
    attachment = ReviewAttachment(id=7, review_id=213, filename="photo.jpg", mime_type="image/jpeg", moderation_status="pending")
    review = _app_review(attachments=[attachment])
    db = Mock(
        execute=AsyncMock(side_effect=[
            _query_result([]),
            _query_result([(SimpleNamespace(system_id=variant_key), product)]),
            _query_result([review]),
            _query_result([(review, product_key, None, None, None)]),
        ]),
        flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock(),
    )
    remote = Mock(request=AsyncMock(side_effect=[
        {"reviews": [{
            "remote_id": 111, "app_review_id": 213, "product_system_id": str(variant_key),
            "rating": 2, "text": "Older website text", "answer": "Спасибо", "status": "published",
            "updated_at": "2026-07-29T09:00:00Z",
            "attachments": [{"app_attachment_id": 7, "website_file_id": 812}],
        }]},
        {"results": [{"app_review_id": 213, "remote_id": 111, "outcome": "updated", "updated_at": "2026-07-29T11:00:00Z"}]},
    ]))
    cache = Mock(bump_namespace=AsyncMock())
    monkeypatch.setattr(sync, "WebsiteReviewSyncClient", lambda: remote)
    monkeypatch.setattr(sync, "get_cache_service", lambda: cache)
    monkeypatch.setattr(utils, "PUBLIC_API_BASE_URL", "https://api.example.test")

    stats = asyncio.run(sync_reviews_with_website(db))

    assert stats.pulled == stats.updated_from_website == stats.conflicts == stats.pushed == 1
    assert stats.attachments_linked == stats.updated_on_website == 1
    assert stats.imported == 0
    assert review.text == "Local edit"
    assert review.moderated is True
    assert review.answer == "Спасибо"
    assert review.website_review_id == 111
    assert review.updated_at == review.website_updated_at == datetime(2026, 7, 29, 11, tzinfo=timezone.utc)
    assert attachment.website_file_id == 812
    assert attachment.moderation_status == "approved"
    event = db.add.call_args.args[0]
    assert isinstance(event, ReviewModerationEvent)
    assert event.action == "review.publish"
    payload = remote.request.call_args.args[1]["reviews"][0]
    assert payload["text"] == "Local edit"
    assert payload["status"] == "published"
    assert payload["product_system_id"] == str(product_key)
    assert payload["attachments"][0]["website_file_id"] == 812
    db.commit.assert_awaited_once()
    db.rollback.assert_not_awaited()
    assert [call.args[0] for call in cache.bump_namespace.await_args_list] == ["reviews", "product", "catalog"]


def test_sync_rolls_back_and_removes_imported_attachment_files_when_push_fails(monkeypatch, tmp_path):
    product_key = UUID("2ea8f4e1-3558-4899-aa99-0de6fc617496")
    imported = []

    def add(obj):
        if isinstance(obj, Review):
            obj.id = 42
            imported.append(obj)

    db = Mock(
        add=Mock(side_effect=add),
        execute=AsyncMock(side_effect=[
            _query_result([SimpleNamespace(id=255, system_id=product_key)]),
            _query_result([]),
            _query_result([(_app_review(), product_key, None, None, None)]),
        ]),
        flush=AsyncMock(), commit=AsyncMock(), rollback=AsyncMock(),
    )
    saved_file = tmp_path / "42" / "photo.jpg"

    async def request(action, payload):
        if action == "pull":
            return {"reviews": [{
                "remote_id": 111, "product_system_id": str(product_key), "rating": 5,
                "status": "published", "updated_at": "2026-07-29T09:00:00Z",
                "attachments": [{"website_file_id": 812, "url": "https://website.test/photo.jpg"}],
            }]}
        assert action == "push"
        assert saved_file.read_bytes() == b"image"
        raise RuntimeError("Website unavailable")

    remote = Mock(request=AsyncMock(side_effect=request))
    cache_factory = Mock()
    monkeypatch.setattr(sync, "WebsiteReviewSyncClient", lambda: remote)
    monkeypatch.setattr(sync, "get_cache_service", cache_factory)
    monkeypatch.setattr(review_attachments, "REVIEWS_MEDIA_DIR", tmp_path)
    monkeypatch.setattr(attachments, "_download_website_attachment", AsyncMock(return_value=("photo.jpg", "image/jpeg", b"image")))

    with pytest.raises(RuntimeError, match="Website unavailable"):
        asyncio.run(sync_reviews_with_website(db))

    assert len(imported) == 1
    assert imported[0].attachments[0].website_file_id == 812
    assert not saved_file.exists()
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
    cache_factory.assert_not_called()


def test_immediate_delivery_failure_returns_false_and_rolls_back(monkeypatch):
    result = Mock()
    result.one_or_none.return_value = (_app_review(), UUID("2ea8f4e1-3558-4899-aa99-0de6fc617496"), None, None, None)
    db = Mock(execute=AsyncMock(return_value=result), rollback=AsyncMock(), commit=AsyncMock())
    remote = Mock(request=AsyncMock(side_effect=RuntimeError("Website unavailable")))
    monkeypatch.setattr(push, "website_review_sync_configured", lambda: True)
    monkeypatch.setattr(push, "WebsiteReviewSyncClient", lambda: remote)

    assert asyncio.run(push.push_review_to_website_safely(db, review_id=213)) is False
    db.rollback.assert_awaited_once()
    db.commit.assert_not_awaited()
