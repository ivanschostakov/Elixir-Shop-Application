import hashlib
import html
import secrets

from datetime import datetime, timedelta
from email.message import EmailMessage

from config import (
    ADMIN_PASSWORD_RESET_EXPIRE_MINUTES,
    ADMIN_PUBLIC_HOST,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    ufa_now,
)


class AdminPasswordResetConfigError(RuntimeError):
    pass


class AdminPasswordResetDeliveryError(RuntimeError):
    pass


def generate_admin_password_reset_token() -> str:
    return secrets.token_urlsafe(48)


def hash_admin_password_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def admin_password_reset_expiry(now: datetime | None = None) -> datetime:
    return (now or ufa_now()) + timedelta(minutes=max(5, ADMIN_PASSWORD_RESET_EXPIRE_MINUTES))


def admin_password_reset_url(token: str) -> str:
    base = (ADMIN_PUBLIC_HOST or "admin-elixirshop.devsivanschostakov.org").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/reset-password#token={token}"


async def send_admin_password_reset_email(
    *,
    to_email: str,
    token: str,
    expires_at: datetime,
) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise AdminPasswordResetConfigError(
            "SMTP_USER and SMTP_PASSWORD are required to send password reset email"
        )
    try:
        import aiosmtplib
    except ModuleNotFoundError as exc:
        raise AdminPasswordResetConfigError(
            "aiosmtplib is required to send password reset email"
        ) from exc

    reset_url = admin_password_reset_url(token)
    expires_text = expires_at.strftime("%d.%m.%Y %H:%M %Z").strip()
    message = EmailMessage()
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = "Восстановление пароля Elixir Shop Admin"
    message.set_content(
        "\n".join(
            (
                "Здравствуйте!",
                "",
                "Получен запрос на восстановление пароля Elixir Shop Admin.",
                f"Ссылка действует до {expires_text}.",
                "",
                f"Изменить пароль: {reset_url}",
                "",
                "Если это были не вы, проигнорируйте письмо. Пароль не изменится.",
                "",
                "English:",
                "A password reset was requested for Elixir Shop Admin.",
                f"The link is valid until {expires_text}.",
                f"Reset password: {reset_url}",
            )
        )
    )
    safe_url = html.escape(reset_url, quote=True)
    message.add_alternative(
        f"""\
<!doctype html>
<html lang="ru">
  <body style="margin:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#172033">
    <div style="max-width:600px;margin:0 auto;padding:32px 18px">
      <div style="background:#fff;border-radius:16px;padding:32px;box-shadow:0 12px 36px rgba(23,32,51,.08)">
        <div style="display:inline-block;background:#0f766e;color:#fff;border-radius:12px;padding:10px 14px;font-weight:700">Elixir Shop Admin</div>
        <h1 style="font-size:26px;margin:28px 0 12px">Восстановление пароля</h1>
        <p style="line-height:1.6">Нажмите кнопку, чтобы задать новый пароль. После смены пароля все активные сеансы админки будут завершены.</p>
        <p style="line-height:1.6"><strong>Ссылка действует до:</strong> {html.escape(expires_text)}</p>
        <p style="margin:28px 0"><a href="{safe_url}" style="display:inline-block;background:#0f766e;color:#fff;text-decoration:none;border-radius:10px;padding:13px 20px;font-weight:700">Изменить пароль</a></p>
        <p style="font-size:13px;line-height:1.5;color:#667085">Если это были не вы, проигнорируйте письмо. Пароль останется прежним.</p>
        <hr style="border:0;border-top:1px solid #e7ebef;margin:24px 0">
        <p style="font-size:13px;line-height:1.5;color:#667085">English: use the button above to reset your password. If you did not request this, ignore this email.</p>
      </div>
    </div>
  </body>
</html>
""",
        subtype="html",
    )
    try:
        await aiosmtplib.send(
            message,
            hostname=SMTP_HOST,
            port=SMTP_PORT,
            start_tls=True,
            username=SMTP_USER,
            password=SMTP_PASSWORD,
            timeout=20,
        )
    except Exception as exc:
        raise AdminPasswordResetDeliveryError("Failed to send password reset email") from exc
