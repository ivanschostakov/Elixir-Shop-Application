import re
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError


def normalize_timezone(value: str) -> str:
    zone = value.strip()
    if zone.upper() in {"UTC", "GMT", "Z"}:
        zone = "UTC"
    elif zone.casefold() in {"мск", "msk", "москва", "moscow"}:
        zone = "Europe/Moscow"
    else:
        # Device/older-client offsets are fixed offsets, never guesses about a
        # city or DST. IANA Etc/GMT has the opposite sign to ordinary UTC offsets.
        offset = re.fullmatch(r"(?:UTC|GMT)?([+-])(\d{1,2})(?::?00)?", zone, re.IGNORECASE)
        if offset and int(offset[2]) <= 14:
            hours = int(offset[2])
            zone = "UTC" if hours == 0 else f"Etc/GMT{'-' if offset[1] == '+' else '+'}{hours}"
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Выберите часовой пояс из списка, например «Москва». Неизвестный часовой пояс.") from error
    return zone
