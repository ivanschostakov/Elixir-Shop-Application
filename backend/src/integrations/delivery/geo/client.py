import json

from httpx import AsyncClient, HTTPError

from config import GEOSUGGEST_API_URL, GEOCODE_API_URL, GEOSUGGEST_API_KEY, GEOCODE_API_KEY
from src.app.services.external_errors import external_service_http_exception
from .schemas import GeoSuggestResult, GeoCodeResult


class GeoClient:
    def __init__(self, geosuggest_api_key: str | None = GEOSUGGEST_API_KEY, geocode_api_key: str | None = GEOCODE_API_KEY):
        self.__geosuggest_api_key = geosuggest_api_key
        self.__geocode_api_key = geocode_api_key
        self._geosuggest_url = GEOSUGGEST_API_URL
        self._geocode_url = GEOCODE_API_URL
        self._client = AsyncClient(timeout=20.0)

    async def aclose(self) -> None:
        await self._client.aclose()

    async def geosuggest(self, text: str, ll: str, lang: str = "ru_RU", v: int = 9, callback: str = "jsonp_ymaps3_suggest_10") -> list[GeoSuggestResult]:
        response = await self._client.get(self._geosuggest_url, params={
            "apikey": self.__geosuggest_api_key,
            "text": text,
            "lang": lang,
            "v": v,
            "callback": callback,
            "ll": ll,
        })
        try: response.raise_for_status()
        except HTTPError as e:
            raise external_service_http_exception(
                service="yandex_geosuggest",
                operation="geosuggest",
                public_detail="Geo suggestion service request failed",
                raw_detail={"status_code": response.status_code, "body": response.text},
                exc=e,
            ) from e
        raw_data: dict = json.loads(response.text.removeprefix("jsonp_ymaps3_suggest_10(").removesuffix(")"))
        if not isinstance(raw_data, dict): raise TypeError(f"Expected dict but got {type(raw_data)}")

        return [GeoSuggestResult.from_raw(r) for r in raw_data["results"]]

    async def geocode(self, address: str, lang: str = "ru_RU", results: int = 1, uri: str | None = None) -> GeoCodeResult:
        params = {
            "apikey": self.__geocode_api_key,
            "geocode": address,
            "format": "json",
            "lang": lang,
            "results": results,
        }
        if uri: params["uri"] = uri

        response = await self._client.get(self._geocode_url, params=params)
        try: response.raise_for_status()
        except HTTPError as e:
            raise external_service_http_exception(
                service="yandex_geocode",
                operation="geocode",
                public_detail="Geo coding service request failed",
                raw_detail={"status_code": response.status_code, "body": response.text},
                exc=e,
            ) from e
        raw_data: dict = response.json()
        if not isinstance(raw_data, dict): raise TypeError(f"Expected dict but got {type(raw_data)}")
        return GeoCodeResult.from_raw(raw_data)

geo_client = GeoClient()
