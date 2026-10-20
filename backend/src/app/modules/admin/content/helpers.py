from fastapi import HTTPException
from starlette import status
from src.app.services.cache import get_cache_service


async def _bump_review_cache() -> None:
    cache = get_cache_service()
    await cache.bump_namespace("reviews")
    await cache.bump_namespace("product")
    await cache.bump_namespace("catalog")


async def _bump_banner_cache() -> None:
    await get_cache_service().bump_namespace("banners")


def _raise_bitrix_review_moderation_authority() -> None:
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "bitrix_review_moderation_authority",
            "message": "Модерация отзывов выполняется в админке сайта Bitrix.",
            "message_ru": "Модерация отзывов выполняется в админке сайта Bitrix.",
            "message_en": "Reviews are moderated in the Bitrix website admin.",
        },
    )
