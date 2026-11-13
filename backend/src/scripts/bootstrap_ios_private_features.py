"""Provision an app-only customer; set its first password via email recovery."""

import argparse
import asyncio
import secrets

from sqlalchemy import func, or_, select

from src.app.services.security import hash_password
from src.database import SessionLocal
from src.database.crud.auth.user import create_user
from src.database.models import AdminIdentity, User
from src.database.schemas.auth.user import UserCreate


async def provision(email: str) -> int:
    data = UserCreate(
        username="admin",
        email=email.strip().lower(),
        password_hash=hash_password(secrets.token_urlsafe(48)),
        name="App",
        surname="Admin",
        is_active=True,
        is_verified=True,
    )
    async with SessionLocal() as db:
        existing = await db.scalar(select(User.id).where(or_(
            func.lower(User.username) == "admin",
            func.lower(User.email) == str(data.email),
        )))
        staff = await db.scalar(select(AdminIdentity.id).where(func.lower(AdminIdentity.email) == str(data.email)))
        if existing is not None or staff is not None:
            raise RuntimeError("Customer or staff identity already exists; refusing to overwrite it")
        user = await create_user(db, data)
        return user.id


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("email")
    args = parser.parse_args()
    print(asyncio.run(provision(args.email)))
