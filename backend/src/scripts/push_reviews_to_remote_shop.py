import argparse
import asyncio
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import bindparam, select, text
from sqlalchemy.ext.asyncio import create_async_engine

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.database import SessionLocal
from src.database.models import Product, Review, ReviewAttachment, User
from src.normalize import optional_str
from src.scripts.remote_shop import remote_shop_database_url


REMOTE_REQUIRED_ENV = (
    "SHOP_POSTGRES_USER",
    "SHOP_POSTGRES_PASSWORD",
    "SHOP_POSTGRES_HOST",
    "SHOP_POSTGRES_DB",
)


@dataclass(frozen=True)
class LocalReviewRow:
    review_id: int
    user_email: str
    user_username: str
    user_password_hash: str
    user_name: str
    user_surname: str
    user_is_active: bool
    user_is_verified: bool
    product_system_id: str
    value: int
    text: str | None
    answer: str | None
    likes: int
    dislikes: int
    moderated: bool
    created_at: Any
    updated_at: Any


@dataclass(frozen=True)
class LocalAttachmentRow:
    review_id: int
    filename: str
    mime_type: str | None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Copy local reviews into remote shop database with deduplication")
    parser.add_argument("--dry-run", action="store_true", help="Plan and print sync stats without writing remote changes")
    parser.add_argument("--limit", type=int, default=None, help="Max local reviews to process")
    parser.add_argument(
        "--create-missing-users",
        action="store_true",
        help="Create users on remote when review author email is missing there",
    )
    return parser.parse_args()


def _ensure_remote_env() -> None:
    missing = [name for name in REMOTE_REQUIRED_ENV if not optional_str(os.getenv(name))]
    if missing:
        missing_csv = ", ".join(missing)
        raise RuntimeError(
            f"Missing remote DB env vars: {missing_csv}. "
            "Set SHOP_POSTGRES_* and rerun."
        )


def _build_review_key(*, user_id: int, product_id: int, value: int, text_value: str | None, created_at: Any) -> tuple[int, int, int, str | None, Any]:
    return (user_id, product_id, value, text_value, created_at)


def _normalize_text_value(value: Any) -> str | None:
    if value is None:
        return None
    normalized = optional_str(value)
    return normalized


async def _load_local_reviews(*, limit: int | None) -> tuple[list[LocalReviewRow], dict[int, list[LocalAttachmentRow]]]:
    async with SessionLocal() as session:
        stmt = (
            select(
                Review.id,
                User.email,
                User.username,
                User.password_hash,
                User.name,
                User.surname,
                User.is_active,
                User.is_verified,
                Product.system_id,
                Review.value,
                Review.text,
                Review.answer,
                Review.likes,
                Review.dislikes,
                Review.moderated,
                Review.created_at,
                Review.updated_at,
            )
            .join(User, User.id == Review.user_id)
            .join(Product, Product.id == Review.product_id)
            .where(Product.system_id.is_not(None))
            .order_by(Review.id.asc())
        )
        if limit is not None and limit > 0:
            stmt = stmt.limit(limit)

        rows = (await session.execute(stmt)).all()
        local_reviews = [
            LocalReviewRow(
                review_id=int(review_id),
                user_email=user_email,
                user_username=user_username,
                user_password_hash=user_password_hash,
                user_name=user_name,
                user_surname=user_surname,
                user_is_active=bool(user_is_active),
                user_is_verified=bool(user_is_verified),
                product_system_id=str(product_system_id),
                value=int(value),
                text=text_value,
                answer=answer_value,
                likes=int(likes or 0),
                dislikes=int(dislikes or 0),
                moderated=bool(moderated),
                created_at=created_at,
                updated_at=updated_at,
            )
            for (
                review_id,
                user_email,
                user_username,
                user_password_hash,
                user_name,
                user_surname,
                user_is_active,
                user_is_verified,
                product_system_id,
                value,
                text_value,
                answer_value,
                likes,
                dislikes,
                moderated,
                created_at,
                updated_at,
            ) in rows
        ]

        review_ids = [row.review_id for row in local_reviews]
        attachments_by_review_id: dict[int, list[LocalAttachmentRow]] = {}
        if review_ids:
            attachments_rows = (
                await session.execute(
                    select(ReviewAttachment.review_id, ReviewAttachment.filename, ReviewAttachment.mime_type).where(
                        ReviewAttachment.review_id.in_(review_ids)
                    )
                )
            ).all()
            for review_id, filename, mime_type in attachments_rows:
                attachment = LocalAttachmentRow(
                    review_id=int(review_id),
                    filename=filename,
                    mime_type=mime_type,
                )
                attachments_by_review_id.setdefault(int(review_id), []).append(attachment)

        return local_reviews, attachments_by_review_id


async def _load_remote_columns(conn, *, table_name: str) -> set[str]:
    rows = (
        await conn.execute(
            text(
                """
                select column_name
                from information_schema.columns
                where table_schema = 'public' and table_name = :table_name
                """
            ),
            {"table_name": table_name},
        )
    ).all()
    return {str(column_name) for (column_name,) in rows}


async def _resolve_remote_product_id_map(conn, *, local_reviews: list[LocalReviewRow]) -> tuple[str, dict[str, int]]:
    product_columns = await _load_remote_columns(conn, table_name="products")
    product_key_column = "system_id" if "system_id" in product_columns else ("onec_id" if "onec_id" in product_columns else "")
    if not product_key_column:
        raise RuntimeError("Remote products table has no system_id/onec_id column for product mapping")

    product_keys = sorted({row.product_system_id for row in local_reviews})
    if not product_keys:
        return product_key_column, {}

    stmt = text(f"select id, {product_key_column} from public.products where {product_key_column} = any(:keys)")
    remote_rows = (
        await conn.execute(
            stmt.bindparams(bindparam("keys", expanding=False)),
            {"keys": product_keys},
        )
    ).all()
    product_id_by_key = {
        str(product_key): int(product_id)
        for product_id, product_key in remote_rows
        if product_key is not None
    }
    return product_key_column, product_id_by_key


async def _load_remote_user_maps(conn) -> tuple[set[str], dict[str, int], set[str]]:
    user_columns = await _load_remote_columns(conn, table_name="users")
    required_for_lookup = {"id", "email"}
    if not required_for_lookup.issubset(user_columns):
        raise RuntimeError("Remote users table must contain id and email")

    remote_user_rows = (await conn.execute(text("select id, email from public.users"))).all()
    email_by_remote_id = {int(user_id): str(email) for user_id, email in remote_user_rows if email is not None}
    user_id_by_email = {email: user_id for user_id, email in email_by_remote_id.items()}
    return user_columns, user_id_by_email, set(email_by_remote_id.values())


async def _create_remote_user_if_missing(conn, *, user_columns: set[str], review: LocalReviewRow, remote_emails: set[str]) -> int | None:
    email = review.user_email
    if email in remote_emails:
        row = (await conn.execute(text("select id from public.users where email = :email"), {"email": email})).first()
        return int(row[0]) if row else None

    insert_fields: dict[str, Any] = {"email": email}

    if "username" in user_columns:
        insert_fields["username"] = review.user_username
    if "password_hash" in user_columns:
        insert_fields["password_hash"] = review.user_password_hash
    if "name" in user_columns:
        insert_fields["name"] = review.user_name
    if "surname" in user_columns:
        insert_fields["surname"] = review.user_surname
    if "is_active" in user_columns:
        insert_fields["is_active"] = review.user_is_active
    if "is_verified" in user_columns:
        insert_fields["is_verified"] = review.user_is_verified

    columns_csv = ", ".join(insert_fields.keys())
    values_csv = ", ".join(f":{key}" for key in insert_fields.keys())
    row = (
        await conn.execute(
            text(f"insert into public.users ({columns_csv}) values ({values_csv}) returning id"),
            insert_fields,
        )
    ).first()
    if row is None:
        return None
    remote_user_id = int(row[0])
    remote_emails.add(email)
    return remote_user_id


async def push_reviews_to_remote_shop(*, dry_run: bool, limit: int | None, create_missing_users: bool) -> None:
    _ensure_remote_env()
    local_reviews, local_attachments_by_review_id = await _load_local_reviews(limit=limit)
    local_reviews_by_id = {row.review_id: row for row in local_reviews}

    remote_engine = create_async_engine(remote_shop_database_url(), pool_pre_ping=True)
    try:
        async with remote_engine.begin() as conn:
            review_columns = await _load_remote_columns(conn, table_name="reviews")
            required_review_columns = {"id", "user_id", "product_id", "value", "created_at"}
            if not required_review_columns.issubset(review_columns):
                raise RuntimeError("Remote reviews table has incompatible schema")

            review_attachment_columns = await _load_remote_columns(conn, table_name="review_attachments")
            has_review_attachments = {"review_id", "filename"}.issubset(review_attachment_columns)

            product_key_column, remote_product_id_by_key = await _resolve_remote_product_id_map(conn, local_reviews=local_reviews)
            user_columns, remote_user_id_by_email, remote_emails = await _load_remote_user_maps(conn)

            rows_total = len(local_reviews)
            skipped_missing_product = 0
            skipped_missing_user = 0
            created_users = 0
            created_reviews = 0
            skipped_duplicates = 0
            created_attachments = 0
            skipped_attachments_duplicates = 0
            skipped_attachments_missing_review = 0

            review_candidates: list[tuple[LocalReviewRow, int, int]] = []
            for review in local_reviews:
                remote_product_id = remote_product_id_by_key.get(review.product_system_id)
                if remote_product_id is None:
                    skipped_missing_product += 1
                    continue

                remote_user_id = remote_user_id_by_email.get(review.user_email)
                if remote_user_id is None and create_missing_users:
                    remote_user_id = await _create_remote_user_if_missing(
                        conn,
                        user_columns=user_columns,
                        review=review,
                        remote_emails=remote_emails,
                    )
                    if remote_user_id is not None:
                        remote_user_id_by_email[review.user_email] = remote_user_id
                        created_users += 1
                if remote_user_id is None:
                    skipped_missing_user += 1
                    continue

                review_candidates.append((review, remote_user_id, remote_product_id))

            candidate_user_ids = sorted({user_id for _, user_id, _ in review_candidates})
            candidate_product_ids = sorted({product_id for _, _, product_id in review_candidates})
            existing_remote_review_by_key: dict[tuple[int, int, int, str | None, Any], int] = {}
            if candidate_user_ids and candidate_product_ids:
                existing_rows = (
                    await conn.execute(
                        text(
                            """
                            select id, user_id, product_id, value, text, created_at
                            from public.reviews
                            where user_id = any(:user_ids) and product_id = any(:product_ids)
                            """
                        ).bindparams(
                            bindparam("user_ids", expanding=False),
                            bindparam("product_ids", expanding=False),
                        ),
                        {"user_ids": candidate_user_ids, "product_ids": candidate_product_ids},
                    )
                ).all()
                for review_id, user_id, product_id, value, text_value, created_at in existing_rows:
                    key = _build_review_key(
                        user_id=int(user_id),
                        product_id=int(product_id),
                        value=int(value),
                        text_value=_normalize_text_value(text_value),
                        created_at=created_at,
                    )
                    existing_remote_review_by_key[key] = int(review_id)

            remote_review_id_by_local_review_id: dict[int, int] = {}
            for review, remote_user_id, remote_product_id in review_candidates:
                review_key = _build_review_key(
                    user_id=remote_user_id,
                    product_id=remote_product_id,
                    value=review.value,
                    text_value=_normalize_text_value(review.text),
                    created_at=review.created_at,
                )
                existing_remote_id = existing_remote_review_by_key.get(review_key)
                if existing_remote_id is not None:
                    remote_review_id_by_local_review_id[review.review_id] = existing_remote_id
                    skipped_duplicates += 1
                    continue

                insert_fields: dict[str, Any] = {
                    "user_id": remote_user_id,
                    "product_id": remote_product_id,
                    "value": review.value,
                    "created_at": review.created_at,
                }
                if "text" in review_columns:
                    insert_fields["text"] = review.text
                if "answer" in review_columns:
                    insert_fields["answer"] = review.answer
                if "likes" in review_columns:
                    insert_fields["likes"] = review.likes
                if "dislikes" in review_columns:
                    insert_fields["dislikes"] = review.dislikes
                if "moderated" in review_columns:
                    insert_fields["moderated"] = review.moderated
                if "updated_at" in review_columns:
                    insert_fields["updated_at"] = review.updated_at

                columns_csv = ", ".join(insert_fields.keys())
                values_csv = ", ".join(f":{key}" for key in insert_fields.keys())
                inserted_row = (
                    await conn.execute(
                        text(f"insert into public.reviews ({columns_csv}) values ({values_csv}) returning id"),
                        insert_fields,
                    )
                ).first()
                if inserted_row is None:
                    continue
                remote_review_id = int(inserted_row[0])
                remote_review_id_by_local_review_id[review.review_id] = remote_review_id
                existing_remote_review_by_key[review_key] = remote_review_id
                created_reviews += 1

            if has_review_attachments:
                target_remote_review_ids = sorted(set(remote_review_id_by_local_review_id.values()))
                existing_attachments: set[tuple[int, str, str | None]] = set()
                if target_remote_review_ids:
                    existing_attachment_rows = (
                        await conn.execute(
                            text(
                                """
                                select review_id, filename, mime_type
                                from public.review_attachments
                                where review_id = any(:review_ids)
                                """
                            ).bindparams(bindparam("review_ids", expanding=False)),
                            {"review_ids": target_remote_review_ids},
                        )
                    ).all()
                    existing_attachments = {
                        (int(review_id), str(filename), _normalize_text_value(mime_type))
                        for review_id, filename, mime_type in existing_attachment_rows
                    }

                for local_review_id, attachments in local_attachments_by_review_id.items():
                    remote_review_id = remote_review_id_by_local_review_id.get(local_review_id)
                    if remote_review_id is None:
                        skipped_attachments_missing_review += len(attachments)
                        continue
                    for attachment in attachments:
                        attachment_key = (
                            remote_review_id,
                            attachment.filename,
                            _normalize_text_value(attachment.mime_type),
                        )
                        if attachment_key in existing_attachments:
                            skipped_attachments_duplicates += 1
                            continue
                        await conn.execute(
                            text(
                                """
                                insert into public.review_attachments (review_id, filename, mime_type)
                                values (:review_id, :filename, :mime_type)
                                """
                            ),
                            {
                                "review_id": remote_review_id,
                                "filename": attachment.filename,
                                "mime_type": attachment.mime_type,
                            },
                        )
                        existing_attachments.add(attachment_key)
                        created_attachments += 1

            if dry_run:
                await conn.rollback()

            print(f"dry_run={dry_run}")
            print(f"remote_product_key_column={product_key_column}")
            print(f"rows_total={rows_total}")
            print(f"rows_mapped_products={len(local_reviews) - skipped_missing_product}")
            print(f"rows_review_candidates={len(review_candidates)}")
            print(f"created_users={created_users}")
            print(f"created_reviews={created_reviews}")
            print(f"skipped_duplicates={skipped_duplicates}")
            print(f"skipped_missing_product={skipped_missing_product}")
            print(f"skipped_missing_user={skipped_missing_user}")
            print(f"created_attachments={created_attachments}")
            print(f"skipped_attachments_duplicates={skipped_attachments_duplicates}")
            print(f"skipped_attachments_missing_review={skipped_attachments_missing_review}")
    finally:
        await remote_engine.dispose()


if __name__ == "__main__":
    args = _parse_args()
    asyncio.run(
        push_reviews_to_remote_shop(
            dry_run=args.dry_run,
            limit=args.limit,
            create_missing_users=args.create_missing_users,
        )
    )
