import hashlib
import html
import secrets

from datetime import datetime, timedelta
from email.message import EmailMessage

from config import (
    ADMIN_INVITATION_EXPIRE_HOURS,
    ADMIN_PUBLIC_HOST,
    SMTP_FROM_NAME,
    SMTP_HOST,
    SMTP_PASSWORD,
    SMTP_PORT,
    SMTP_USER,
    ufa_now,
)
from src.app.services.admin.role_catalog import SYSTEM_ROLE_BY_CODE
from src.database.models import AdminInvitation


class AdminInvitationConfigError(RuntimeError):
    pass


class AdminInvitationDeliveryError(RuntimeError):
    pass


def generate_admin_invitation_token() -> str:
    return secrets.token_urlsafe(48)


def hash_admin_invitation_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def admin_invitation_expiry(now: datetime | None = None) -> datetime:
    return (now or ufa_now()) + timedelta(hours=max(1, ADMIN_INVITATION_EXPIRE_HOURS))


def admin_invitation_status(invitation: AdminInvitation, now: datetime | None = None) -> str:
    if invitation.accepted_at is not None:
        return "accepted"
    if invitation.revoked_at is not None:
        return "revoked"
    if invitation.expires_at <= (now or ufa_now()):
        return "expired"
    return "pending"


def admin_invitation_accept_url(token: str) -> str:
    base = (ADMIN_PUBLIC_HOST or "admin-elixirshop.devsivanschostakov.org").strip().rstrip("/")
    if not base.startswith(("http://", "https://")):
        base = f"https://{base}"
    return f"{base}/accept-invite#token={token}"


def admin_invitation_role_names(role_codes: list[str], locale: str) -> list[str]:
    attribute = "name_ru" if locale == "ru" else "name_en"
    return [
        getattr(SYSTEM_ROLE_BY_CODE[code], attribute)
        for code in role_codes
        if code in SYSTEM_ROLE_BY_CODE
    ]


async def send_admin_invitation_email(
    *,
    to_email: str,
    token: str,
    inviter_name: str,
    role_codes: list[str],
    expires_at: datetime,
) -> None:
    if not SMTP_USER or not SMTP_PASSWORD:
        raise AdminInvitationConfigError("SMTP_USER and SMTP_PASSWORD are required to send admin invitations")
    try:
        import aiosmtplib
    except ModuleNotFoundError as exc:
        raise AdminInvitationConfigError("aiosmtplib is required to send admin invitations") from exc

    role_names = admin_invitation_role_names(role_codes, "ru")
    roles_text = ", ".join(role_names)
    accept_url = admin_invitation_accept_url(token)
    expires_text = expires_at.strftime("%d.%m.%Y %H:%M %Z").strip()

    message = EmailMessage()
    message["From"] = f"{SMTP_FROM_NAME} <{SMTP_USER}>"
    message["To"] = to_email
    message["Subject"] = "Приглашение в Elixir Shop Admin"
    message.set_content(
        "\n".join(
            (
                "Здравствуйте!",
                "",
                f"{inviter_name} приглашает вас в Elixir Shop Admin.",
                f"Роли: {roles_text}.",
                f"Ссылка действует до {expires_text}.",
                "",
                f"Принять приглашение: {accept_url}",
                "",
                "Если вы не ожидали это письмо, просто проигнорируйте его.",
            )
        )
    )
    safe_url = html.escape(accept_url, quote=True)
    message.add_alternative(
        f"""\
<!doctype html>
<html lang="ru">
  <body style="margin:0;background:#f4f6f8;font-family:Arial,sans-serif;color:#172033">
    <div style="max-width:600px;margin:0 auto;padding:32px 18px">
      <div style="background:#ffffff;border-radius:16px;padding:32px;box-shadow:0 12px 36px rgba(23,32,51,.08)">
        <div style="display:inline-block;background:#0f766e;color:#fff;border-radius:12px;padding:10px 14px;font-weight:700">Elixir Shop Admin</div>
        <h1 style="font-size:26px;margin:28px 0 12px">Вас пригласили в команду</h1>
        <p style="line-height:1.6">{html.escape(inviter_name)} назначил вам доступ к административной панели.</p>
        <p style="line-height:1.6"><strong>Роли:</strong> {html.escape(roles_text)}</p>
        <p style="line-height:1.6"><strong>Ссылка действует до:</strong> {html.escape(expires_text)}</p>
        <p style="margin:28px 0">
          <a href="{safe_url}" style="display:inline-block;background:#0f766e;color:#fff;text-decoration:none;border-radius:10px;padding:13px 20px;font-weight:700">Принять приглашение</a>
        </p>
        <p style="font-size:13px;line-height:1.5;color:#667085">После создания доступа при первом входе нужно настроить MFA. Если вы не ожидали это письмо, проигнорируйте его.</p>
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
        raise AdminInvitationDeliveryError("Failed to send admin invitation email") from exc
