import argparse
import asyncio
import csv
import html
import secrets
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from uuid import UUID

from sqlalchemy import select

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from config import UFA_TZ
from src.app.services.security import hash_password
from src.database import SessionLocal
from src.database.models import Product, Review, User
from src.normalize import coerce_int, optional_str

PRODUCT_SYSTEM_ID_COLUMN = 2
RATING_COLUMN = 4
TEXT_COLUMN = 6
LIKES_COLUMN = 9
DISLIKES_COLUMN = 10
DATE_CREATION_COLUMN = 11
DATE_CHANGE_COLUMN = 12
MODERATED_COLUMN = 13

PLACEHOLDER_USER_ID = 0
PLACEHOLDER_USERNAME = "site_reviews"
PLACEHOLDER_EMAIL = "site-reviews+placeholder@elixir.local"
PLACEHOLDER_NAME = "С сайта"


@dataclass(frozen=True)
class SourceReviewRow:
    product_system_id: UUID
    value: int
    text: str | None
    likes: int
    dislikes: int
    moderated: bool
    created_at: datetime
    updated_at: datetime


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Import external website reviews CSV into local reviews table")
    parser.add_argument("--csv-path", type=Path, required=True, help="Path to external reviews CSV")
    parser.add_argument("--dry-run", action="store_true", help="Parse and plan import without writing to DB")
    return parser.parse_args()


def _row_value(row: list[str], index: int) -> str | None:
    if index >= len(row):
        return None
    return optional_str(row[index])


def _parse_datetime(raw: str | None) -> datetime | None:
    if raw is None:
        return None

    for dt_format in ("%Y-%m-%d %H:%M:%S", "%d.%m.%Y %H:%M:%S"):
        try:
            return datetime.strptime(raw, dt_format).replace(tzinfo=UFA_TZ)
        except ValueError:
            continue
    return None


def _normalize_text(raw: str | None) -> str | None:
    normalized = optional_str(html.unescape(raw or ""))
    return normalized if normalized else None


def _parse_moderated_flag(raw: str | None) -> bool:
    return (raw or "").strip().upper() == "Y"


def _load_source_reviews(csv_path: Path) -> tuple[list[SourceReviewRow], dict[str, int]]:
    counters = {
        "rows_total": 0,
        "rows_empty": 0,
        "rows_invalid_product_system_id": 0,
        "rows_invalid_rating": 0,
        "rows_invalid_dates": 0,
    }
    parsed: list[SourceReviewRow] = []

    with csv_path.open("r", encoding="utf-8-sig", newline="") as source_file:
        reader = csv.reader(source_file)
        next(reader, None)

        for row in reader:
            counters["rows_total"] += 1

            product_system_id_raw = _row_value(row, PRODUCT_SYSTEM_ID_COLUMN)
            rating_raw = _row_value(row, RATING_COLUMN)
            text_raw = _row_value(row, TEXT_COLUMN)
            likes_raw = _row_value(row, LIKES_COLUMN)
            dislikes_raw = _row_value(row, DISLIKES_COLUMN)
            date_creation_raw = _row_value(row, DATE_CREATION_COLUMN)
            date_change_raw = _row_value(row, DATE_CHANGE_COLUMN)
            moderated_raw = _row_value(row, MODERATED_COLUMN)

            if product_system_id_raw is None and rating_raw is None and text_raw is None:
                counters["rows_empty"] += 1
                continue

            try:
                product_system_id = UUID(product_system_id_raw or "")
            except ValueError:
                counters["rows_invalid_product_system_id"] += 1
                continue

            value = coerce_int(rating_raw)
            if value is None or value < 0 or value > 5:
                counters["rows_invalid_rating"] += 1
                continue

            created_at = _parse_datetime(date_creation_raw)
            changed_at = _parse_datetime(date_change_raw)
            if created_at is None:
                counters["rows_invalid_dates"] += 1
                continue

            parsed.append(
                SourceReviewRow(
                    product_system_id=product_system_id,
                    value=value,
                    text=_normalize_text(text_raw),
                    likes=max(coerce_int(likes_raw) or 0, 0),
                    dislikes=max(coerce_int(dislikes_raw) or 0, 0),
                    moderated=_parse_moderated_flag(moderated_raw),
                    created_at=created_at,
                    updated_at=changed_at or created_at,
                )
            )

    return parsed, counters


async def _ensure_placeholder_user(session) -> User:
    user = await session.get(User, PLACEHOLDER_USER_ID)
    if user is not None:
        return user

    user = User(
        id=PLACEHOLDER_USER_ID,
        username=PLACEHOLDER_USERNAME,
        email=PLACEHOLDER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(32)),
        name=PLACEHOLDER_NAME,
        surname=PLACEHOLDER_NAME,
        is_active=False,
        is_verified=True,
        last_active_at=None,
    )
    session.add(user)
    await session.flush()
    return user


async def import_reviews_from_website_csv(csv_path: Path, *, dry_run: bool) -> None:
    source_reviews, counters = _load_source_reviews(csv_path)
    source_product_ids = {item.product_system_id for item in source_reviews}

    async with SessionLocal() as session:
        await _ensure_placeholder_user(session)

        products = list((await session.execute(select(Product).where(Product.system_id.in_(source_product_ids)))).scalars().all())
        product_id_by_system_id = {product.system_id: product.id for product in products if product.system_id is not None}

        product_ids = [product.id for product in products]
        existing_keys: set[tuple[int, int, str | None, datetime]] = set()
        if product_ids:
            existing_reviews = list(
                (
                    await session.execute(
                        select(Review.product_id, Review.value, Review.text, Review.created_at).where(
                            Review.user_id == PLACEHOLDER_USER_ID,
                            Review.product_id.in_(product_ids),
                        )
                    )
                ).all()
            )
            existing_keys = {(product_id, value, text, created_at) for product_id, value, text, created_at in existing_reviews}

        created_reviews = 0
        skipped_missing_products = 0
        skipped_duplicates = 0

        for source_review in source_reviews:
            product_id = product_id_by_system_id.get(source_review.product_system_id)
            if product_id is None:
                skipped_missing_products += 1
                continue

            review_key = (product_id, source_review.value, source_review.text, source_review.created_at)
            if review_key in existing_keys:
                skipped_duplicates += 1
                continue

            session.add(
                Review(
                    user_id=PLACEHOLDER_USER_ID,
                    product_id=product_id,
                    value=source_review.value,
                    text=source_review.text,
                    answer=None,
                    likes=source_review.likes,
                    dislikes=source_review.dislikes,
                    moderated=source_review.moderated,
                    created_at=source_review.created_at,
                    updated_at=source_review.updated_at,
                )
            )
            existing_keys.add(review_key)
            created_reviews += 1

        if dry_run:
            await session.rollback()
        else:
            await session.commit()

    print(f"csv_path={csv_path}")
    print(f"dry_run={dry_run}")
    print(f"rows_total={counters['rows_total']}")
    print(f"rows_empty={counters['rows_empty']}")
    print(f"rows_invalid_product_system_id={counters['rows_invalid_product_system_id']}")
    print(f"rows_invalid_rating={counters['rows_invalid_rating']}")
    print(f"rows_invalid_dates={counters['rows_invalid_dates']}")
    print(f"rows_valid={len(source_reviews)}")
    print(f"mapped_products={len(product_ids)}")
    print(f"created_reviews={created_reviews}")
    print(f"skipped_missing_products={skipped_missing_products}")
    print(f"skipped_duplicates={skipped_duplicates}")


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(import_reviews_from_website_csv(args.csv_path, dry_run=args.dry_run))
