from pydantic import BaseModel, Field
from typing import Literal

class AppIntegrityChallengeCreate(BaseModel):
    purpose: Literal["attestation", "assertion"]
    action: str | None = Field(default=None, max_length=32)


class AppIntegrityChallengeRead(BaseModel):
    challenge: str


class IosAppAttestRegisterPayload(BaseModel):
    key_id: str = Field(min_length=1, max_length=128)
    challenge: str = Field(min_length=1, max_length=128)
    attestation_object: str = Field(min_length=1)


class IosAppAttestRegisterRead(BaseModel):
    key_id: str
    environment: str