from pydantic import BaseModel, EmailStr, Field


class UserRegisterPayload(BaseModel):
    username: str = Field(min_length=1, max_length=16)
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)
