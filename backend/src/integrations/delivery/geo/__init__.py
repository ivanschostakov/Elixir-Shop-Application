from .client import GeoClient, geo_client


def get_geo_client() -> GeoClient:
    return geo_client


__all__ = [
    "GeoClient",
    "get_geo_client",
]
