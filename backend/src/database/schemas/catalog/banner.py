from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from src.database.limits import BANNER_IMAGE_PATH_MAX_LENGTH, BANNER_LINK_MAX_LENGTH


class BannerBase(BaseModel):
    image_path: str = Field(min_length=1, max_length=BANNER_IMAGE_PATH_MAX_LENGTH)
    desktop_image_path: str | None = Field(default=None, max_length=BANNER_IMAGE_PATH_MAX_LENGTH)
    mobile_image_path: str | None = Field(default=None, max_length=BANNER_IMAGE_PATH_MAX_LENGTH)
    title: str | None = Field(default=None, max_length=240)
    inner_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    outer_link: str | None = Field(default=None, max_length=BANNER_LINK_MAX_LENGTH)
    priority: int = Field(default=0, ge=0)
    archived: bool = False
    status: str = "published"
    starts_at: datetime | None = None
    ends_at: datetime | None = None


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
    click_count: int = 0
    impression_count: int = 0
    created_at: datetime
    updated_at: datetime
