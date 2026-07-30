from __future__ import annotations

import os
import sys
from pathlib import Path


TARGETS = {
    "BITRIX_PROMO_ENDPOINT": "https://elixirpeptide.com:8443/bitrix/tools/elixir.promo/api.php",
    "BITRIX_PROMO_TOKEN": os.environ.get("ELIXIR_PROMO_TOKEN", ""),
    "BITRIX_PROMO_TIMEOUT_SECONDS": "15",
    "BITRIX_DELIVERY_ENDPOINT": "https://elixirpeptide.com:8443/bitrix/tools/elixir.delivery/quote.php",
    "BITRIX_DELIVERY_SECRET": os.environ.get("ELIXIR_DELIVERY_SECRET", ""),
    "BITRIX_DELIVERY_TIMEOUT_SECONDS": "30",
    "WEBSITE_IDENTITY_ENDPOINT": "https://elixirpeptide.com:8443/local/api/app_integration.php",
    "WEBSITE_IDENTITY_TOKEN": os.environ.get("ELIXIR_APP_TOKEN", ""),
    "WEBSITE_IDENTITY_TIMEOUT_SECONDS": "15",
    "AUTH_LOGIN_WEBSITE_FIRST_ENABLED": "true",
    "WEBSITE_REVIEW_SYNC_ENDPOINT": "https://elixirpeptide.com:8443/bitrix/tools/elixir.reviewsync/sync.php",
    "WEBSITE_REVIEW_SYNC_SECRET": os.environ.get("ELIXIR_REVIEW_SECRET", ""),
    "WEBSITE_REVIEW_SYNC_INTERVAL_MINUTES": "1",
    "WEBSITE_REVIEW_SYNC_TIMEOUT_SECONDS": "30",
    "WEBSITE_CATALOG_SYNC_ENDPOINT": "https://elixirpeptide.com:8443/bitrix/tools/elixir.catalogsync/sync.php",
    "WEBSITE_CATALOG_SYNC_SECRET": os.environ.get("ELIXIR_CATALOG_SECRET", ""),
    "WEBSITE_CATALOG_PUBLIC_BASE_URL": "https://elixirpeptide.com",
    "WEBSITE_CATALOG_SYNC_INTERVAL_MINUTES": "5",
    "WEBSITE_CATALOG_SYNC_TIMEOUT_SECONDS": "30",
}
REMOVE_KEYS = {"BITRIX_PROXY_URL"}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: configure_app_env.py <backend/.env>")
    for name in (
        "BITRIX_PROMO_TOKEN",
        "BITRIX_DELIVERY_SECRET",
        "WEBSITE_IDENTITY_TOKEN",
        "WEBSITE_REVIEW_SYNC_SECRET",
        "WEBSITE_CATALOG_SYNC_SECRET",
    ):
        if len(TARGETS[name]) < 32:
            raise SystemExit(f"Missing or weak secret: {name}")

    path = Path(sys.argv[1]).resolve()
    original = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(TARGETS)
    updated: list[str] = []
    for line in original:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in REMOVE_KEYS:
            continue
        if key in remaining:
            updated.append(f"{key}={remaining.pop(key)}")
        else:
            updated.append(line)
    if remaining:
        if updated and updated[-1] != "":
            updated.append("")
        updated.extend(f"{key}={value}" for key, value in remaining.items())

    temporary = path.with_name(path.name + ".elixir-new")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)
    print("APP_ENV_CONFIGURED")


if __name__ == "__main__":
    main()
