import secrets

from email.message import EmailMessage

from config import SMTP_FROM_NAME, SMTP_HOST, SMTP_PASSWORD, SMTP_PORT, SMTP_USER
from src.app.services.security.context import hash_value, verify_value


class EmailVerificationConfigError(RuntimeError):
    pass


class EmailVerificationDeliveryError(RuntimeError):
    pass


def generate_email_verification_code() -> str:
    return f"{secrets.randbelow(1_000_000):06d}"


def hash_email_verification_code(code: str) -> str:
    return hash_value(code)


def verify_email_verification_code(code: str, code_hash: str) -> bool:
    return verify_value(code, code_hash)


async def send_user_verification_code_email(*, to_email: str, code: str) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise EmailVerificationConfigError("SMTP_USER and SMTP_PASSWORD are required to send verification email")

    try:
        import aiosmtplib
    except ModuleNotFoundError as exc:
        raise EmailVerificationConfigError("aiosmtplib is required to send verification email") from exc

    msg = EmailMessage()
    msg["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = "Код подтверждения"
    msg.set_content(
        f"""Здравствуйте!

Ваш код подтверждения: {code}
Если вы не запрашивали код, свяжитесь с поддержкой."""
    )

    try:
        await aiosmtplib.send(
            msg,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            timeout=20,
        )
    except Exception as exc:
        raise EmailVerificationDeliveryError("Failed to send verification email") from exc
