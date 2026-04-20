import asyncio

import httpx

from integrations.delivery.cdek import cdek_client

url = "https://api.cdek.ru/v2/calculator/tariff"
asyncio.run(cdek_client.get_access_token())
token = cdek_client._access_token
print(token)

payload = {
    "type": 1,
    "tariff_code": 136,
    "currency": "RUB",
    "from_location": {"code": 44},
    "to_location": {"code": 270},
    "packages": [
        {
            "weight": 1000,
            "length": 20,
            "width": 15,
            "height": 10
        }
    ]
}

headers = {
    "Authorization": f"Bearer {token}",
    "Content-Type": "application/json",
}

with httpx.Client(timeout=30) as client:
    resp = client.post(url, json=payload, headers=headers)
    print(resp.status_code)
    print(resp.json())