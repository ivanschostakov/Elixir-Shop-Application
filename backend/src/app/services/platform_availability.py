"""Client platform detection for the documented catalog scope."""
from collections.abc import Mapping

CATALOG_VARY = "Authorization, X-App-Platform, X-App-Integrity-Platform, User-Agent"


def mobile_shop_request(headers: Mapping[str, str]) -> bool:
    return headers.get("x-app-platform", headers.get("x-app-integrity-platform", "")).lower() in {"ios", "android"}


def is_ios_request(headers: Mapping[str, str]) -> bool:
    platform = headers.get("x-app-platform", headers.get("x-app-integrity-platform", "")).lower()
    # Older native clients may not yet send X-App-Platform. Do not classify
    # desktop/admin/web requests as iOS merely because of a Safari user-agent.
    agent = headers.get("user-agent", "").lower()
    return platform == "ios" or (not platform and ("iphone" in agent or "ipad" in agent))
