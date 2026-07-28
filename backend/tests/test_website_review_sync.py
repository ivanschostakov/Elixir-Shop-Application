from datetime import datetime, timezone
from types import SimpleNamespace

from src.integrations import website_reviews
from src.integrations.website_reviews import (
    _push_payload,
    _remote_values,
    _review_state,
    _valid_website_attachment_url,
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


def test_push_payload_contains_public_attachment_urls(monkeypatch):
    monkeypatch.setattr(
        website_reviews,
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
        "url": "https://api.example.test/media/reviews/42/photo.jpg",
        "filename": "photo.jpg",
        "mime_type": "image/jpeg",
    }]


def test_website_attachment_url_is_restricted_to_sotbit_uploads(monkeypatch):
    monkeypatch.setattr(
        website_reviews,
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
