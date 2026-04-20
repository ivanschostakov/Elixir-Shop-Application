from datetime import datetime, timedelta, timezone

from jose import JWTError, jwt

from config import JWT_ACCESS_EXPIRE_MINUTES, JWT_ACCESS_SECRET_KEY

ALGORITHM = "HS256"


def create_access_token(user_id: int, session_id: int) -> str:
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(minutes=JWT_ACCESS_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "sid": str(session_id), "type": "access", "iat": now, "exp": expires_at}
    return jwt.encode(payload, JWT_ACCESS_SECRET_KEY, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict | None:
    try: return jwt.decode(token, JWT_ACCESS_SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError: return None
