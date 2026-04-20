from pydantic import BaseModel, EmailStr, Field, TypeAdapter, ValidationError


class UserLoginPayload(BaseModel):
    login: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=128)

    @property
    def is_email(self) -> bool:
        try:
            TypeAdapter(EmailStr).validate_python(self.login)
            return True
        except ValidationError: return False
