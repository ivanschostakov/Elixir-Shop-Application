from typing import Generic, TypeVar
from pydantic import BaseModel, EmailStr


T = TypeVar("T")


class AdminPage(BaseModel, Generic[T]):
    items: list[T]
    total: int
    limit: int
    offset: int


class CustomerCompact(BaseModel):
    id: int
    username: str | None = None
    name: str
    surname: str
    email: EmailStr | None = None
    phone_number: str | None = None
