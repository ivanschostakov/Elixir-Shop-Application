from fastapi import APIRouter, Depends, HTTPException, Query
from starlette import status

from src.app.services.cache import build_cache_key, get_cache_service
from src.integrations.delivery.geo import GeoClient, get_geo_client
from src.integrations.delivery.geo.schemas import GeoCodeResult, GeoSuggestResult

geo_router = APIRouter(prefix="/geo", tags=["geo"])
GEO_SUGGEST_CACHE_TTL_SECONDS = 10 * 60


def _normalize_ll_key(ll: str) -> str:
    raw_parts = [part.strip() for part in ll.split(",", 1)]
    if len(raw_parts) != 2:
        return ll.strip()
    try:
        lon = round(float(raw_parts[0]), 4)
        lat = round(float(raw_parts[1]), 4)
    except ValueError:
        return ll.strip()
    return f"{lon:.4f},{lat:.4f}"


@geo_router.get("/suggest", response_model=list[GeoSuggestResult], status_code=status.HTTP_200_OK)
async def suggest(
    query: str = Query(..., min_length=1, description="User search text"),
    ll: str = Query(..., description="Coordinates in format 'lon,lat'"),
    lang: str = Query("ru_RU"),
    version: int = Query(9, ge=1, alias="v"),
    geo: GeoClient = Depends(get_geo_client),
) -> list[GeoSuggestResult]:
    cache = get_cache_service()
    base_key = build_cache_key(
        route="delivery:geo:suggest",
        params={
            "query": query.strip().lower(),
            "ll": _normalize_ll_key(ll),
            "lang": lang.strip(),
            "v": version,
        },
    )
    cache_key = await cache.versioned_key("delivery_geo", base_key)
    cached_items = await cache.get_json(cache_key, key_prefix="delivery:geo:suggest")
    if cached_items is not None:
        return [GeoSuggestResult.model_validate(item) for item in cached_items]

    items = await geo.geosuggest(text=query, ll=ll, lang=lang, v=version)
    await cache.set_json(
        cache_key,
        [item.model_dump(mode="json") for item in items],
        ttl_seconds=GEO_SUGGEST_CACHE_TTL_SECONDS,
        key_prefix="delivery:geo:suggest",
    )
    return items


@geo_router.get("/code", response_model=GeoCodeResult, status_code=status.HTTP_200_OK)
async def code(
    address: str = Query(..., min_length=1),
    uri: str | None = Query(None),
    lang: str = Query("ru_RU"),
    results: int = Query(1, ge=1, le=10),
    geo: GeoClient = Depends(get_geo_client),
) -> GeoCodeResult:
    try: return await geo.geocode(address=address, uri=uri, lang=lang, results=results)
    except ValueError as exc: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
