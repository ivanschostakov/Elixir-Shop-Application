"""Preview by default. --apply requires a new, private backup file on a persistent volume."""
import argparse
import asyncio
import json
import os
from datetime import timedelta

from sqlalchemy import select

from src.database import SessionLocal
from src.database.models import EmailVerificationCode, User, UserDevice, UserSession
from . import app_welcome as promo


def candidates():
    # used_at is set only after successful email-code verification. Pair it
    # with session issuance and native device registration for the SAME user.
    s, c, d = UserSession, EmailVerificationCode, UserDevice
    verified_native = select(s.id).join(c, c.user_id == s.user_id).join(d, d.user_id == s.user_id).where(
        s.user_id == User.id, s.purpose == "app", c.used_at >= promo.START,
        s.created_at.between(c.used_at - timedelta(seconds=2), c.used_at + timedelta(minutes=2)),
        d.platform.in_(("ios", "android")),
        d.first_seen_at.between(s.created_at - timedelta(seconds=2), s.created_at + timedelta(minutes=3)),
    ).exists()
    return select(User).where(
        User.is_active.is_(True), User.is_verified.is_(True), User.email.is_not(None),
        ~promo.blocked_identity(User.email, User.moysklad_counterparty_id), verified_native,
    ).order_by(User.id)


async def run(backup=None):
    async with SessionLocal() as db:
        query = candidates()
        users = (await db.scalars(query)).all()
        if not backup:
            return {"eligible": len(users)}
        # No email, password or token is required to identify or undo this batch.
        before = [{"user_id": u.id, "welcome_bonus_granted_at": None, "credit_before": None,
                   "key": f"welcome:user:{u.id}"} for u in users]
        with os.fdopen(os.open(backup, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
            json.dump(before, out)
            out.flush()
            os.fsync(out.fileno())
        added = []
        for user in users:
            credit_id = await promo.grant_on_email_confirmation(db, user)
            if credit_id is not None:
                added.append({"user_id": user.id, "credit_id": credit_id})
        with os.fdopen(os.open(backup + ".insertions", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
            json.dump(added, out)
            out.flush()
            os.fsync(out.fileno())
        await db.commit()
        return {"eligible": len(users), "granted": len(added)}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", metavar="BACKUP_FILE")
    print(asyncio.run(run(parser.parse_args().apply)))
