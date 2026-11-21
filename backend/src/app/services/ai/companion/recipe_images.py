"""Public Commons photos. Only generic dish terms leave the application.

API: https://www.mediawiki.org/wiki/API:Imageinfo
License metadata: https://commons.wikimedia.org/wiki/Help:Machine-readable_data
"""
import html
import re
import time
from urllib.parse import urlsplit, urlunsplit

import httpx

from .food_suggestions import RecipeImage

_cache = {}
_ttl = 86400
_agent = "ElixirNutrition/1.0 (recipe photograph search; Wikimedia Commons)"


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


async def find_recipe_image(query):
    # Generated queries are constrained to public English dish names; never accept URLs.
    if not re.fullmatch(r"[A-Za-z][A-Za-z ' -]{2,79}", query):
        return None
    key = query.lower().strip()
    cached = _cache.get(key)
    if cached and cached[0] > time.monotonic():
        return cached[1]
    image = None
    try:
        async with httpx.AsyncClient(timeout=8, headers={"User-Agent": _agent}, follow_redirects=False) as client:
            # Exact dish first, then a shorter dish search when Commons has no match.
            for terms in dict.fromkeys((key, " ".join(key.split()[:2]))):
                response = await client.get("https://commons.wikimedia.org/w/api.php", params={"action": "query", "generator": "search", "gsrnamespace": 6, "gsrsearch": terms + " filetype:bitmap", "gsrlimit": 4, "prop": "imageinfo", "iiprop": "url|extmetadata|mime", "iiextmetadatafilter": "Artist|LicenseShortName", "iiurlwidth": 800, "format": "json"})
                response.raise_for_status()
                pages = response.json().get("query", {}).get("pages", {}).values()
                for page in sorted(pages, key=lambda item: item.get("index", 100)):
                    image = commons_image(page)
                    if image:
                        break
                if image:
                    break
    except (httpx.HTTPError, ValueError, TypeError, AttributeError):
        return None  # A photo outage must not discard an already calculated recipe.
    if len(_cache) >= 256:
        _cache.pop(next(iter(_cache)))
    _cache[key] = (time.monotonic() + (_ttl if image else 300), image)
    return image
