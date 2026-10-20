from typing import Any


def _normalize_reaction_emoji(emoji: str) -> str:
    normalized = emoji.strip()
    # Telegram sends the heart without a variation selector, while the app's
    # picker uses the emoji presentation form. Treat them as one reaction.
    if normalized in {"❤", "❤️"}: return "❤️"
    return normalized


def _telegram_reaction_emoji(reaction_type: object) -> str | None:
    if not isinstance(reaction_type, dict): return None
    kind = str(reaction_type.get("type") or "")
    if kind == "emoji":
        emoji = _normalize_reaction_emoji(str(reaction_type.get("emoji") or ""))
        return emoji or None
    if kind == "paid": return "⭐"
    # Telegram custom emoji need their sticker document to render correctly;
    # they are deliberately not mislabeled as a different Unicode reaction.
    return None


def _telegram_reaction_actor_key(update: dict[str, Any]) -> str | None:
    user = update.get("user") if isinstance(update.get("user"), dict) else None
    actor_chat = update.get("actor_chat") if isinstance(update.get("actor_chat"), dict) else None
    if user and int(user.get("id") or 0): return f"user:{int(user['id'])}"
    if actor_chat and int(actor_chat.get("id") or 0): return f"chat:{int(actor_chat['id'])}"
    return None
