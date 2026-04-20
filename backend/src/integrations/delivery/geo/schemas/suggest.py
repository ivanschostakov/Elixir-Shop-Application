from typing import Any
from pydantic import BaseModel, ConfigDict, computed_field


class GeoSuggestResult(BaseModel):
    type: str
    title: str
    subtitle: str
    full_address: str
    tags: list[str] = []
    uri: str | None = None
    action: str | None = None
    button_text: str | None = None
    distance_text: str | None = None
    distance_value: float | None = None

    model_config = ConfigDict(extra="ignore")

    @classmethod
    def from_raw(cls, data: dict[str, Any]) -> "GeosuggestItem":
        distance = data.get("distance", {}) or {}
        title = data.get("title", {}) or {}
        subtitle = data.get("subtitle", {}) or {}

        return cls(
            type=data.get("type", ""),
            title=title.get("text", ""),
            subtitle=subtitle.get("text", ""),
            full_address=f"{title.get('text', '')} {subtitle.get('text', '')}",
            tags=data.get("tags", []),
            uri=data.get("uri"),
            action=data.get("action"),
            button_text=data.get("button_text"),
            distance_text=distance.get("text"),
            distance_value=distance.get("value"),
        )

    @computed_field
    @property
    def primary_tag(self) -> str | None:
        return self.tags[0] if self.tags else None

    @computed_field
    @property
    def is_business(self) -> bool:
        return self.type == "business"

    @computed_field
    @property
    def is_toponym(self) -> bool:
        return self.type == "toponym"

    @computed_field
    @property
    def display_subtitle(self) -> str:
        if self.distance_text and self.subtitle: return f"{self.subtitle} · {self.distance_text}"
        if self.distance_text: return self.distance_text
        return self.subtitle

    @computed_field
    @property
    def icon_key(self) -> str:
        if self.type == "business":
            if "supermarket" in self.tags:
                return "store"
            if "cafe" in self.tags or "fast food" in self.tags:
                return "food"
            return "business"

        if "house" in self.tags:
            return "house"
        if "street" in self.tags:
            return "street"
        if "metro" in self.tags:
            return "metro"
        if "district" in self.tags:
            return "district"
        if "locality" in self.tags:
            return "locality"
        if "province" in self.tags:
            return "province"
        if "country" in self.tags:
            return "country"
        if "vegetation" in self.tags:
            return "vegetation"

        return "place"