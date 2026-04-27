from typing import Literal
from pydantic import ConfigDict
from .common import AmoBaseSchema


class RefreshTokenRequest(AmoBaseSchema):
    client_id: str
    client_secret: str
    grant_type: Literal["refresh_token"] = "refresh_token"
    redirect_uri: str
    refresh_token: str


class AuthorizationCodeRequest(AmoBaseSchema):
    client_id: str
    client_secret: str
    grant_type: Literal["authorization_code"] = "authorization_code"
    redirect_uri: str
    code: str


class OAuthTokenResponse(AmoBaseSchema):
    model_config = ConfigDict(extra="ignore")

    token_type: str | None = None
    expires_in: int | None = None
    access_token: str
    refresh_token: str
    server_time: int | None = None
