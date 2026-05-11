from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import BANNER_IMAGE_PATH_MAX_LENGTH, BANNER_LINK_MAX_LENGTH


class BannerBase(BaseModel):
    image_path: str = Field(min_length=1, max_length=BANNER_IMAGE_PATH_MAX_LENGTH)
    inner_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    outer_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    priority: int = Field(default=0, ge=0)
    archived: bool = False


class BannerCreate(BannerBase):
    pass


class BannerUpdate(BaseModel):
    image_path: str | None = Field(default=None, min_length=1, max_length=BANNER_IMAGE_PATH_MAX_LENGTH)
    inner_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    outer_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    priority: int | None = Field(default=None, ge=0)
    archived: bool | None = None


class BannerRead(BannerBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime
