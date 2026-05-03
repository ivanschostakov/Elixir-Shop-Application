from typing import Any
from pydantic import BaseModel, ConfigDict


class GeoBoundsPoint(BaseModel):
    lat: float
    lon: float


class GeoBounds(BaseModel):
    south_west: GeoBoundsPoint
    north_east: GeoBoundsPoint


class GeoCodeResult(BaseModel):
    address: str
    title: str
    subtitle: str
    city: str | None = None
    kind: str
    precision: str | None = None
    country_code: str | None = None
    lat: float
    lon: float
    bounds: GeoBounds | None = None
    uri: str | None = None
    postal_code: str | None = None

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> "GeocodeItem":
        collection = data.get("response", {}).get("GeoObjectCollection", {})
        members = collection.get("featureMember", [])
        if not members: raise ValueError("No geocode results found")

        geo_object = members[0].get("GeoObject", {})
        meta = geo_object.get("metaDataProperty", {}).get("GeocoderMetaData", {})
        address = meta.get("Address", {}) or {}
        envelope = geo_object.get("boundedBy", {}).get("Envelope", {}) or {}

        pos = geo_object.get("Point", {}).get("pos", "")
        lon, lat = map(float, pos.split())

        return cls(
            address=meta.get("text", ""),
            title=geo_object.get("name", ""),
            subtitle=geo_object.get("description", ""),
            city=parse_city(address),
            kind=meta.get("kind", ""),
            precision=meta.get("precision"),
            country_code=parse_country_code(address),
            lat=lat,
            lon=lon,
            bounds=parse_geo_bounds(envelope),
            uri=geo_object.get("uri"),
            postal_code=address.get("postal_code"),
        )


def parse_geo_bounds(envelope: dict[str, Any]) -> GeoBounds | None:
    lower_corner = envelope.get("lowerCorner")
    upper_corner = envelope.get("upperCorner")
    if not lower_corner or not upper_corner: return None

    south_west_lon, south_west_lat = map(float, lower_corner.split())
    north_east_lon, north_east_lat = map(float, upper_corner.split())

    return GeoBounds(
        south_west=GeoBoundsPoint(
            lat=south_west_lat,
            lon=south_west_lon,
        ),
        north_east=GeoBoundsPoint(
            lat=north_east_lat,
            lon=north_east_lon,
        ),
    )


def parse_country_code(address: dict[str, Any]) -> str | None:
    country_code = address.get("country_code")
    if not isinstance(country_code, str): return None
    normalized_country_code = country_code.strip().upper()
    return normalized_country_code or None


def parse_city(address: dict[str, Any]) -> str | None:
    return (
        parse_address_component(address, {"locality"})
        or parse_address_component(address, {"province"})
        or parse_address_component(address, {"area"})
        or parse_address_component(address, {"district"})
    )


def parse_address_component(address: dict[str, Any], kinds: set[str]) -> str | None:
    components = address.get("Components")
    if not isinstance(components, list): return None

    for component in components:
        if not isinstance(component, dict): continue
        if component.get("kind") not in kinds: continue
        name = component.get("name")
        if isinstance(name, str):
            normalized_name = name.strip()
            if normalized_name: return normalized_name

    return None
