import asyncio
import json
import os

import httpx

API_KEY = os.getenv("GEOSUGGEST_API_KEY", "").strip()
YANDEX_GEOSUGGEST_URL = "https://suggest-maps.yandex.ru/suggest-geo"

TEST_CASES = [
    "Мос",
    "Твер",
    "Арба",
    "Киевс",
    "Пяте",
    "Соч",
    "Лени",
    "Невс",
    "Каза",
    "Екат",
]


async def geosuggest(text: str) -> str:
    if not API_KEY:
        raise RuntimeError("GEOSUGGEST_API_KEY must be set before running this integration check")
    params = {
        "apikey": API_KEY,
        "text": text,
        "lang": "ru_RU",
        "v": 9,
        "callback": "jsonp_ymaps3_suggest_10",
        "ll": "37.6176,55.7558"
    }

    async with httpx.AsyncClient(timeout=10.0) as client:
        response = await client.get(YANDEX_GEOSUGGEST_URL, params=params)
        response.raise_for_status()
        return response.text


async def main() -> None:
    for query in TEST_CASES:
        print(f"\n=== QUERY: {query} ===")
        result = await geosuggest(query)
        with open(f"{query}.json", "w", encoding="utf-8") as f: json.dump(json.loads(result.removeprefix("jsonp_ymaps3_suggest_10(").removesuffix(")")), f, ensure_ascii=False, indent=4)




if __name__ == "__main__":
    import httpx

    url = "https://geocode-maps.yandex.ru/v1/"
    params = {
        "apikey": os.getenv("GEOCODE_API_KEY", "").strip(),
        "geocode": "Санкт-Петербург, Приморский проспект, 72",
        "format": "json",
        "lang": "ru_RU",
        "results": 5,
    }

    if not params["apikey"]:
        raise RuntimeError("GEOCODE_API_KEY must be set before running this integration check")

    with httpx.Client(timeout=10.0) as client:
        r = client.get(url, params=params)
        print(r.status_code)
        print(r.text)
