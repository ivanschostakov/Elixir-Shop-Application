from pydantic import BaseModel, Field, field_validator

from src.app.services.recent_searches import normalize_recent_search_query


class CreateRecentSearchQueryPayload(BaseModel):
    query: str = Field(min_length=1, max_length=100)

    @field_validator("query")
    @classmethod
    def normalize_query(cls, value: str) -> str:
        normalized = normalize_recent_search_query(value)
        if not normalized:
            raise ValueError("Query cannot be empty")
        return normalized


__all__ = ["CreateRecentSearchQueryPayload"]
