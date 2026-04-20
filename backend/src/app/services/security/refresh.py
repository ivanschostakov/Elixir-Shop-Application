import secrets

from src.app.services.security.context import hash_value, verify_value


def create_refresh_token() -> str:
    return secrets.token_urlsafe(64)


def hash_refresh_token(refresh_token: str) -> str:
    return hash_value(refresh_token)


def verify_refresh_token(refresh_token: str, refresh_token_hash: str) -> bool:
    return verify_value(refresh_token, refresh_token_hash)
