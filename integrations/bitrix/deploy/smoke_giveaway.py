from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta


async def main() -> None:
    repo = os.environ.get("ELIXIR_GIVEAWAY_REPO", "")
    if repo:
        sys.path.insert(0, repo)

    from src.integrations.bitrix24.client import AsyncBitrix24

    email = os.environ["ELIXIR_SMOKE_EMAIL"]
    async with AsyncBitrix24() as client:
        user_id = await client.get_user_id_by_email(email)
        reviews = await client.find_reviews(
            user_id,
            datetime.now() - timedelta(days=2),
            min_grade=5,
            min_length=10,
        )
    if not reviews or not any("ELIXIR_SMOKE_REVIEW" in review.text for review in reviews):
        raise RuntimeError("Giveaway endpoint did not return the smoke review")
    print(json.dumps({"get_user_id": "ok", "find_review": "ok", "matched_reviews": len(reviews)}))


if __name__ == "__main__":
    asyncio.run(main())
