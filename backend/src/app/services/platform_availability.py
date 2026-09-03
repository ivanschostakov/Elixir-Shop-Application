"""iOS catalog availability; not an authentication or reviewer-detection mechanism."""
from collections.abc import Mapping
import re

from starlette.responses import JSONResponse, Response

import config

CATALOG_VARY = "X-App-Platform, X-App-Integrity-Platform, User-Agent"
_EMPTY_LIST_PATHS = {
    "/api/v1/products", "/api/v1/product-categories", "/api/v1/banners",
    "/api/v1/favorites/products", "/api/v1/users/me/favorites/products",
    "/api/v1/users/me/recommendations", "/api/v1/users/me/promotions",
    "/api/v1/users/me/order-drafts", "/api/v1/users/me/search-queries",
}


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
        "/api/v1/users/me/search-queries",
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


def catalog_response(headers: Mapping[str, str], path: str, method: str) -> Response | None:
    """Empty catalog data, not a client feature flag or an alternative UI."""
    if method == "OPTIONS" or not is_commerce_blocked(headers, path, method):
        return None
    path = path.rstrip("/")
    response_headers = {"Cache-Control": "no-store", "Vary": CATALOG_VARY}
    # Basket handlers preserve authentication and the existing object contract.
    if (path == "/api/v1/users/me/basket" and method in {"GET", "POST"}) or (
        path == "/api/v1/guest/basket/quote" and method == "POST"
    ):
        return None
    if path in {"/api/v1/users/me/basket/checkout/options", "/api/v1/guest/phone/check"}:
        return None
    if method == "GET":
        if path in _EMPTY_LIST_PATHS or re.fullmatch(r"/api/v1/products/\d+/(similar|reviews)", path):
            return JSONResponse([], headers=response_headers)
        if re.fullmatch(r"/api/v1/products/\d+/questions", path):
            return JSONResponse({"items": [], "total": 0}, headers=response_headers)
        # Detail endpoints return objects, not arrays. Use their normal missing
        # state so an old deep link cannot render [] as a Product/OrderDraft.
        return JSONResponse({"detail": "Not found"}, status_code=404, headers=response_headers)
    # Do not count impressions/clicks from previously cached ads or products.
    if method == "POST" and (
        re.fullmatch(r"/api/v1/banners/\d+/(click|impression)", path)
        or path in {"/api/v1/users/me/recommendations/views", "/api/v1/users/me/recommendations/categories/views"}
    ):
        return Response(status_code=204, headers=response_headers)
    # Never acknowledge a new order or cart mutation as a successful empty list.
    return JSONResponse({"detail": {
        "code": "ios_catalog_unavailable",
        "message": "Catalog and purchases are unavailable on iOS.",
    }}, status_code=403, headers=response_headers)


def empty_basket_payload(*, user_id: int, basket_id: int = 0, created_at=None, updated_at=None) -> dict:
    """Read-only empty view; never clear the customer's stored basket."""
    now = config.ufa_now()
    return {
        "id": basket_id, "user_id": user_id, "items": [],
        "items_count": 0, "total_quantity": 0,
        "total_amount": 0, "delivery_total": 0, "grand_total": 0,
        "currency": "RUB", "has_unavailable_items": False,
        "created_at": created_at or now, "updated_at": updated_at or now,
    }


def allow_push_for_platform(platform: str | None, data: dict) -> bool:
    if not config.APPLE_DEV_MODE or (platform or "").lower() != "ios":
        return True
    # A custom campaign must not evade the restriction by omitting its type.
    return data.get("type") in {"order_status_changed", "support_reply", "ai_companion"}
