from __future__ import annotations

import sys
from pathlib import Path


ENDPOINT = "https://elixirpeptide.com:8443/bitrix/tools/elixir.delivery/quote.php"


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit("Usage: configure_delivery_env.py <backend/.env> <secret-file>")

    env_path = Path(sys.argv[1]).resolve()
    secret_path = Path(sys.argv[2]).resolve()
    secret = secret_path.read_text(encoding="utf-8").strip()
    if len(secret) < 32:
        raise SystemExit("Missing or weak delivery secret")

    targets = {
        "BITRIX_DELIVERY_ENDPOINT": ENDPOINT,
        "BITRIX_DELIVERY_SECRET": secret,
        "BITRIX_DELIVERY_TIMEOUT_SECONDS": "30",
    }
    original = env_path.read_text(encoding="utf-8").splitlines()
    remaining = dict(targets)
    updated: list[str] = []
    for line in original:
        key = line.split("=", 1)[0].strip() if "=" in line and not line.lstrip().startswith("#") else None
        if key in remaining:
            updated.append(f"{key}={remaining.pop(key)}")
        else:
            updated.append(line)
    if remaining:
        if updated and updated[-1] != "":
            updated.append("")
        updated.extend(f"{key}={value}" for key, value in remaining.items())

    temporary = env_path.with_name(env_path.name + ".elixir-delivery-new")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    temporary.chmod(env_path.stat().st_mode & 0o777)
    temporary.replace(env_path)
    print("DELIVERY_ENV_CONFIGURED")


if __name__ == "__main__":
    main()
