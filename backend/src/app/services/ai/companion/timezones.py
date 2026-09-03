import re
from datetime import timedelta, timezone
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
        offset = re.fullmatch(r"(?:UTC|GMT)?([+-])(\d{1,2})(?::?(\d{2}))?", zone, re.IGNORECASE)
        if offset:
            hours, minutes = int(offset[2]), int(offset[3] or 0)
            if hours > 14 or minutes > 59 or hours == 14 and minutes:
                raise ValueError("Некорректный часовой пояс устройства")
            if minutes:
                return f"UTC{offset[1]}{hours:02}:{minutes:02}"
            zone = "UTC" if hours == 0 else f"Etc/GMT{'-' if offset[1] == '+' else '+'}{hours}"
    try:
        ZoneInfo(zone)
    except (ZoneInfoNotFoundError, ValueError) as error:
        raise ValueError("Не удалось определить часовой пояс устройства") from error
    return zone


def timezone_info(value: str):
    zone = normalize_timezone(value)
    if zone.startswith("UTC+") or zone.startswith("UTC-"):
        minutes = int(zone[4:6]) * 60 + int(zone[7:9])
        return timezone(timedelta(minutes=minutes if zone[3] == "+" else -minutes))
    return ZoneInfo(zone)
