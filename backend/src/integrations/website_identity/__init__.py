__all__ = [
    "WebsiteIdentityClient",
    "WebsiteIdentityError",
    "get_website_identity_client",
    "website_identity_client",
]

from .client import WebsiteIdentityClient, website_identity_client
from .exceptions import WebsiteIdentityError


def get_website_identity_client() -> WebsiteIdentityClient:
    return website_identity_client
