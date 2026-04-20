from .context import hash_value, verify_value


def hash_password(password: str) -> str:
    return hash_value(password)


def verify_password(password: str, password_hash: str) -> bool:
    return verify_value(password, password_hash)
