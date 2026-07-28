from __future__ import annotations

import os
import sys
from pathlib import Path


TARGETS = {
    "BITRIX24_BASE_URL": "https://elixirpeptide.com:8443",
    "BITRIX24_ENDPOINT": "/local/api/giveaways.php",
    "BITRIX24_TOKEN": os.environ.get("ELIXIR_GIVEAWAY_TOKEN", ""),
}


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("Usage: configure_giveaway_env.py <.env>")
    if len(TARGETS["BITRIX24_TOKEN"]) < 32:
        raise SystemExit("Missing or weak giveaway token")

    path = Path(sys.argv[1]).resolve()
    original = path.read_text(encoding="utf-8").splitlines()
    remaining = dict(TARGETS)
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

    temporary = path.with_name(path.name + ".elixir-new")
    temporary.write_text("\n".join(updated) + "\n", encoding="utf-8")
    temporary.chmod(path.stat().st_mode & 0o777)
    temporary.replace(path)
    print("GIVEAWAY_ENV_CONFIGURED")


if __name__ == "__main__":
    main()
