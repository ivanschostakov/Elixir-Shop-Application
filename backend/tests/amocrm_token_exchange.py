import os

import httpx

required = [
    "AMOCRM_BASE_DOMAIN",
    "AMOCRM_CLIENT_ID",
    "AMOCRM_CLIENT_SECRET",
    "AMOCRM_REDIRECT_URI",
    "AMOCRM_REFRESH_TOKEN",
]
missing = [name for name in required if not os.getenv(name)]
if missing:
    raise SystemExit(f"Missing env vars: {', '.join(missing)}")

base = os.environ["AMOCRM_BASE_DOMAIN"]
payload = {
    "client_id": os.environ["AMOCRM_CLIENT_ID"],
    "client_secret": os.environ["AMOCRM_CLIENT_SECRET"],
    "grant_type": "refresh_token",
    "refresh_token": os.environ["AMOCRM_REFRESH_TOKEN"],
    "redirect_uri": os.environ["AMOCRM_REDIRECT_URI"],
}

proxy = os.getenv("AMOCRM_PROXY_URL") or None
with httpx.Client(timeout=30, proxy=proxy) as client:
    response = client.post(f"https://{base}/oauth2/access_token", json=payload)

print("status:", response.status_code)
print("content-type:", response.headers.get("content-type"))
print(response.text[:2000])

raise SystemExit(0 if response.is_success else 1)
