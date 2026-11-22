"""Public Commons photos. Only generic dish terms leave the application.

API: https://www.mediawiki.org/wiki/API:Imageinfo
License metadata: https://commons.wikimedia.org/wiki/Help:Machine-readable_data
"""
import html
import re
import time
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

import httpx

from .food_suggestions import RecipeImage

_cache = {}
_ttl = 86400
_agent = "ElixirNutrition/1.0 (recipe photograph search; Wikimedia Commons)"
MAX_CANDIDATES = 4
MAX_PHOTO_BYTES = 2 * 1024 * 1024


@dataclass(frozen=True)
class RecipePhotoCandidate:
    image: RecipeImage
    title: str


async def load_recipe_photo(url, *, client):
    parsed = urlsplit(url)
    if parsed.scheme != "https" or parsed.netloc not in {"upload.wikimedia.org", "thumb.wikimedia.org"} or not parsed.path.startswith("/wikipedia/commons/"):
        return None
    try:
        async with client.stream("GET", url, follow_redirects=False) as response:
            response.raise_for_status()
            if int(response.headers.get("content-length", 0)) > MAX_PHOTO_BYTES:
                return None
            data = bytearray()
            async for chunk in response.aiter_bytes():
                if len(data) + len(chunk) > MAX_PHOTO_BYTES:
                    return None
                data.extend(chunk)
        raw = bytes(data)
        mime = "image/jpeg" if raw.startswith(b"\xff\xd8\xff") else "image/png" if raw.startswith(b"\x89PNG\r\n\x1a\n") else "image/webp" if raw.startswith(b"RIFF") and raw[8:12] == b"WEBP" else None
        return (mime, raw) if mime else None
    except (httpx.HTTPError, ValueError, TypeError):
        return None


def plain(value):
    return html.unescape(re.sub(r"<[^>]*>", "", value or "")).strip()[:300]


def commons_image(page):
    for info in page.get("imageinfo", []):
        meta = info.get("extmetadata", {})
        license_name = plain(meta.get("LicenseShortName", {}).get("value"))
        if not re.fullmatch(r"CC (?:BY(?:-SA)? [1-4]\.0|0)|Public domain", license_name):
            continue
        if info.get("mime") not in {"image/jpeg", "image/png", "image/webp"}:
            continue
        photo = urlsplit(info.get("thumburl") or "")
        source = urlsplit(info.get("descriptionurl") or "")
        if photo.scheme != "https" or photo.netloc not in {"upload.wikimedia.org", "thumb.wikimedia.org"} or not photo.path.startswith("/wikipedia/commons/"):
            continue
        if source.scheme != "https" or source.netloc != "commons.wikimedia.org" or not source.path.startswith("/wiki/File:"):
            continue
        return RecipeImage(url=urlunsplit((photo.scheme, photo.netloc, photo.path, "", "")), source_url=urlunsplit((source.scheme, source.netloc, source.path, "", "")), author=plain(meta.get("Artist", {}).get("value")), license=license_name)
    return None


async def find_recipe_candidates(query):
    # Generated queries are constrained to public English dish names; never accept URLs.
    if not re.fullmatch(r"[A-Za-z][A-Za-z ' -]{2,79}", query):
        return []
    key = query.lower().strip()
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    candidates = []
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": _agent}, follow_redirects=False) as client:
            # Keep the complete dish: dropping garnish/preparation caused unrelated photos.
            response = await client.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": key + " filetype:bitmap", "gsrlimit": 8, "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiextmetadatafilter": "Artist|LicenseShortName", "iiurlwidth": 800, "format": "json"})
            response.raise_for_status()
            pages = response.json().get("query", {}).get("pages", {}).values()
            words = set(re.findall(r"[a-z]+", key)) - {"and", "with", "the", "of", "on", "a"}
            def rank(page):
                title = set(re.findall(r"[a-z]+", page.get("title", "").lower()))
                return (-len(words & title), page.get("index", 100))
            seen = set()
            for page in sorted(pages, key=rank):
                photo = commons_image(page)
                if photo and photo.url not in seen:
                    candidates.append(RecipePhotoCandidate(image=photo, title=plain(page.get("title", ""))))
                    seen.add(photo.url)
                if len(candidates) == MAX_CANDIDATES:
                    break
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return []  # A photo outage must not discard an already calculated recipe.
    if len(_cache) >= 256:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic() + (_ttl if candidates else 300), candidates)
    return candidates
