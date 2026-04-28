from pydantic import BaseModel, EmailStr, Field


class UserRegisterPayload(BaseModel):
    username: str = Field(min_length=1, max_length=16)
    email: EmailStr
    password: str = Field(min_length=1, max_length=100)
    name: str = Field(min_length=1, max_length=100)
    surname: str = Field(min_length=1, max_length=100)


class UserRegisterVerifyPayload(BaseModel):
    email: EmailStr
    code: str = Field(min_length=6, max_length=6, pattern=r"^\d{6}$")


class UserVerificationCodeResendPayload(BaseModel):
    email: EmailStr


class UserRegistrationStartedResponse(BaseModel):
    user_id: int
    email: EmailStr
    verification_required: bool = True
    message: str


class UserVerificationCodeSentResponse(BaseModel):
    email: EmailStr
    verification_required: bool = True
    message: str
