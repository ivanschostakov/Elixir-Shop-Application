from fastapi import APIRouter, Depends, Query
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.modules.users.me.schemas import CreateRecentSearchQueryPayload
from src.app.services.recent_searches import (
    RECENT_SEARCHES_DEFAULT_LIMIT,
    RECENT_SEARCHES_MAX_ITEMS,
    add_recent_search_query,
    clear_recent_search_queries,
    list_recent_search_queries,
)
from src.database.models import User

search_queries_router = APIRouter(prefix="/search-queries", tags=["my_search_queries"])


@search_queries_router.get("", response_model=list[str], status_code=status.HTTP_200_OK)
async def list_my_recent_search_queries(limit: int = Query(default=RECENT_SEARCHES_DEFAULT_LIMIT, ge=1, le=RECENT_SEARCHES_MAX_ITEMS), current_user: User = Depends(get_current_user)) -> list[str]: return await list_recent_search_queries(user_id=current_user.id, limit=limit)


@search_queries_router.post("", status_code=status.HTTP_204_NO_CONTENT)
async def add_my_recent_search_query(payload: CreateRecentSearchQueryPayload, current_user: User = Depends(get_current_user)) -> None: await add_recent_search_query(user_id=current_user.id, query=payload.query)


@search_queries_router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_my_recent_search_queries(current_user: User = Depends(get_current_user)) -> None: await clear_recent_search_queries(user_id=current_user.id)


__all__ = ["search_queries_router"]
