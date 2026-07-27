from datetime import datetime, timezone
from types import SimpleNamespace

from src.integrations.website_reviews import _remote_values, _review_state


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
