from datetime import datetime, timezone
from types import SimpleNamespace

from starlette.requests import Request

from src.app.main import app
from src.app.modules.products.helpers import (
    serialize_product_question,
    serialize_review,
)
from src.app.services import review_attachments
from src.database.schemas import ReviewCreate
from src.integrations.website_reviews import _push_payload


def _request() -> Request:
    return Request({
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": [],
        "query_string": b"",
        "server": ("testserver", 80),
        "scheme": "http",
    })


def test_product_question_routes_include_public_and_admin_moderation():
    paths = app.openapi()["paths"]

    assert {"get", "post"} <= set(paths["/api/v1/products/{product_id}/questions"])
    assert "get" in paths["/api/v1/admin/questions"]
    assert "patch" in paths["/api/v1/admin/questions/{question_id}/moderation"]


def test_review_anonymity_is_part_of_create_and_public_read_contract():
    payload = ReviewCreate(value=5, text="Отлично", hide_sender_name=True)
    assert payload.hide_sender_name is True

    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    review = SimpleNamespace(
        id=4,
        product_id=8,
        value=5,
        text="Отлично",
        answer=None,
        attachments=[],
        likes=0,
        dislikes=0,
        moderated=True,
        hide_sender_name=True,
        user=SimpleNamespace(
            name="Настоящее имя",
            phone_number=None,
            email="customer@example.test",
        ),
        guest_name=None,
        created_at=now,
        updated_at=now,
    )

    serialized = serialize_review(_request(), review)

    assert serialized.is_anonymous is True
    assert serialized.author_username == "Анонимный покупатель"


def test_anonymous_review_is_also_anonymous_in_bitrix_payload():
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    review = SimpleNamespace(
        id=5,
        website_review_id=None,
        value=4,
        text="Хорошо",
        answer=None,
        likes=0,
        dislikes=0,
        rejected_at=None,
        moderated=False,
        guest_name=None,
        guest_email=None,
        hide_sender_name=True,
        attachments=[],
        created_at=now,
        updated_at=now,
    )

    payload = _push_payload(
        review,
        system_id="2ea8f4e1-3558-4899-aa99-0de6fc617496",
        email="customer@example.test",
        name="Настоящее",
        surname="Имя",
    )

    assert payload["author_name"] == "Анонимный покупатель"


def test_product_question_serialization_keeps_answer_and_author():
    now = datetime(2026, 7, 30, tzinfo=timezone.utc)
    question = SimpleNamespace(
        id=7,
        product_id=11,
        text="Как хранить?",
        answer="В прохладном месте.",
        user=SimpleNamespace(
            name="Анна",
            phone_number=None,
            email="anna@example.test",
        ),
        guest_name=None,
        created_at=now,
        updated_at=now,
    )

    serialized = serialize_product_question(question)

    assert serialized.author_username == "Анна"
    assert serialized.answer == "В прохладном месте."


def test_review_attachment_url_uses_public_api_base(
    monkeypatch,
    tmp_path,
):
    media_dir = tmp_path / "media"
    image_path = media_dir / "reviews" / "64" / "photo.jpg"
    image_path.parent.mkdir(parents=True)
    image_path.write_bytes(b"image")
    monkeypatch.setattr(review_attachments, "MEDIA_DIR", media_dir)
    monkeypatch.setattr(
        review_attachments,
        "PUBLIC_API_BASE_URL",
        "https://api.example.test",
    )

    url = review_attachments.build_review_attachment_url(_request(), image_path)

    assert url.startswith(
        "https://api.example.test/media/reviews/64/photo.jpg?v=",
    )
