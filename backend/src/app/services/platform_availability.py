"""iOS catalog availability; not an authentication or reviewer-detection mechanism."""
from collections.abc import Mapping

import config


def is_ios_request(headers: Mapping[str, str]) -> bool:
    platform = headers.get("x-app-platform", headers.get("x-app-integrity-platform", "")).lower()
    # Older native clients may not yet send X-App-Platform. Do not classify
    # desktop/admin/web requests as iOS merely because of a Safari user-agent.
    agent = headers.get("user-agent", "").lower()
    return platform == "ios" or (not platform and ("iphone" in agent or "ipad" in agent))


def is_commerce_path(path: str, method: str = "GET") -> bool:
    path = path.rstrip("/")
    roots = (
        "/api/v1/products", "/api/v1/product-categories", "/api/v1/banners",
        "/api/v1/favorites", "/api/v1/favourites", "/api/v1/guest",
        "/api/v1/stock-subscriptions",
        "/api/v1/users/me/basket", "/api/v1/users/me/order-drafts",
        "/api/v1/users/me/favorites",
        "/api/v1/users/me/stock-subscriptions",
        "/api/v1/users/me/recommendations", "/api/v1/users/me/promotions",
        "/api/v1/users/me/benefits", "/api/v1/users/me/search-queries",
        "/api/v1/users/me/ai-chat/actions",
    )
    if any(path == root or path.startswith(root + "/") for root in roots):
        return True
    # Preserve existing-order history and support; prevent new/repeated orders.
    return method == "POST" and (
        path == "/api/v1/users/me/orders"
        or (path.startswith("/api/v1/users/me/orders/") and path.endswith("/repeat"))
    )


def is_commerce_blocked(headers: Mapping[str, str], path: str, method: str) -> bool:
    return config.APPLE_DEV_MODE and is_ios_request(headers) and is_commerce_path(path, method)


def allow_push_for_platform(platform: str | None, data: dict) -> bool:
    if not config.APPLE_DEV_MODE or (platform or "").lower() != "ios":
        return True
    # A custom campaign must not evade the restriction by omitting its type.
    return data.get("type") in {"order_status_changed", "support_reply"}
