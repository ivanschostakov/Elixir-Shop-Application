"""Create an app-only review customer without any admin role or site changes."""

import argparse
import asyncio
from getpass import getpass

from sqlalchemy import func, or_, select

from src.app.services.security import hash_password
from src.database import SessionLocal
from src.database.crud.auth.user import create_user
from src.database.models import AdminIdentity, User
from src.database.schemas.auth.user import UserCreate


async def bootstrap_app_review(*, email: str, username: str, password: str) -> int:
    if username.strip() != "app-review":
        raise ValueError("The App Review customer must use the app-review username")
    if len(password) < 16:
        raise ValueError("Use a unique password of at least 16 characters")
    data = UserCreate(
        email=email.strip().lower(),
        username=username.strip(),
        name="Apple",
        surname="Reviewer",
        password_hash=hash_password(password),
        is_active=True,
        is_verified=True,
    )
    async with SessionLocal() as db:
        customer = await db.scalar(select(User.id).where(or_(
            func.lower(User.email) == str(data.email).lower(),
            func.lower(User.username) == data.username.lower(),
        )))
        admin = await db.scalar(select(AdminIdentity.id).where(
            func.lower(AdminIdentity.email) == str(data.email).lower(),
        ))
        if customer is not None or admin is not None:
            raise RuntimeError("Identity already exists; refusing to overwrite it")
        user = await create_user(db, data)
        return user.id


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    parser.add_argument("--username", default="app-review", choices=["app-review"])
    args = parser.parse_args()
    password = getpass("New unique App Review password (at least 16 characters): ")
    user_id = await bootstrap_app_review(email=args.email, username=args.username, password=password)
    print(f"App Review customer created: username=app-review, customer_id={user_id}")
    print("No feature flags or environment overrides are required.")


if __name__ == "__main__":
    asyncio.run(main())
