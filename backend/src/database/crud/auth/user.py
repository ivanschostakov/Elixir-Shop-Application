from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.database.models import Basket
from src.database.models import User
from src.database.schemas import UserCreate, UserUpdate


async def create_user(session: AsyncSession, data: UserCreate, *, commit: bool = True) -> User:
    values = data.model_dump()
    if not values.get("username") and values.get("email"):
        values["username"] = values["email"]
    user = User(**values)
    user.basket = Basket()
    session.add(user)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(user)
    return user


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    return (await session.execute(select(User).where(User.id == user_id))).scalar_one_or_none()


async def get_user_by_email(session: AsyncSession, email: str | None) -> User | None:
    if not email:
        return None
    return (await session.execute(select(User).where(User.email == email))).scalar_one_or_none()


async def get_user_by_username(session: AsyncSession, username: str | None) -> User | None:
    normalized = str(username or "").strip().casefold()
    if not normalized:
        return None
    return (
        await session.execute(select(User).where(func.lower(User.username) == normalized))
    ).scalar_one_or_none()


async def get_user_by_phone_number(session: AsyncSession, phone_number: str | None) -> User | None:
    if not phone_number:
        return None
    return (await session.execute(select(User).where(User.phone_number == phone_number))).scalar_one_or_none()


async def get_user_by_telegram_user_id(session: AsyncSession, telegram_user_id: int) -> User | None:
    return (await session.execute(select(User).where(User.telegram_user_id == telegram_user_id))).scalar_one_or_none()


async def get_users(session: AsyncSession, *, q: str | None = None, is_active: bool | None = None, is_verified: bool | None = None, offset: int = 0, limit: int = 100) -> list[User]:
    stmt = select(User)
    if is_active is not None: stmt = stmt.where(User.is_active == is_active)
    if is_verified is not None: stmt = stmt.where(User.is_verified == is_verified)
    if q:
        stmt = stmt.where(
            or_(
                User.username.ilike(f"%{q}%"),
                User.email.ilike(f"%{q}%"),
                User.name.ilike(f"%{q}%"),
                User.surname.ilike(f"%{q}%"),
                User.phone_number.ilike(f"%{q}%"),
            )
        )
    stmt = stmt.order_by(User.id.desc()).offset(offset).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def update_user(session: AsyncSession, user: User, data: UserUpdate, *, commit: bool = True) -> User:
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    if commit:
        await session.commit()
    else:
        await session.flush()
    await session.refresh(user)
    return user


async def delete_user(session: AsyncSession, user: User) -> None:
    await session.delete(user)
    await session.commit()
