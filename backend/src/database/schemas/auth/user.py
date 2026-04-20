from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from config import ufa_now

from src.database.limits import EMAIL_MAX_LENGTH, PASSWORD_HASH_MAX_LENGTH, PERSON_NAME_MAX_LENGTH, PHONE_NUMBER_MAX_LENGTH, USERNAME_MAX_LENGTH


class UserBase(BaseModel):
    username: str = Field(min_length=1, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr = Field(max_length=EMAIL_MAX_LENGTH)
    name: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str = Field(min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    phone_number: str | None = Field(default=None, max_length=PHONE_NUMBER_MAX_LENGTH)


class UserCreate(UserBase):
    password_hash: str = Field(min_length=1, max_length=PASSWORD_HASH_MAX_LENGTH)
    is_active: bool = True
    last_active_at: datetime = Field(default_factory=ufa_now)
    is_verified: bool = False


class UserUpdate(BaseModel):
    username: str | None = Field(default=None, min_length=1, max_length=USERNAME_MAX_LENGTH)
    email: EmailStr | None = Field(default=None, max_length=EMAIL_MAX_LENGTH)
    password_hash: str | None = Field(default=None, min_length=1, max_length=PASSWORD_HASH_MAX_LENGTH)
    name: str | None = Field(default=None, min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    surname: str | None = Field(default=None, min_length=1, max_length=PERSON_NAME_MAX_LENGTH)
    is_active: bool | None = None
    last_active_at: datetime | None = None
    is_verified: bool | None = None
    phone_number: str | None = Field(default=None, max_length=PHONE_NUMBER_MAX_LENGTH)


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    last_active_at: datetime | None
    is_verified: bool
    created_at: datetime
    updated_at: datetime
