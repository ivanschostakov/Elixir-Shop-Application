from passlib.context import CryptContext

pwd_context = CryptContext(schemes=["scrypt"], deprecated="auto", scrypt__rounds=16, scrypt__block_size=8, scrypt__parallelism=1)


def hash_value(value: str) -> str:
    return pwd_context.hash(value)


def verify_value(value: str, value_hash: str) -> bool:
    return pwd_context.verify(value, value_hash)
