from fastapi import APIRouter, Depends, File, Request, UploadFile
from starlette import status

from src.app.modules.auth.dependencies import get_current_user
from src.app.services.avatar_storage import (
    build_avatar_url,
    convert_avatar_to_png,
    find_avatar_path,
    remove_existing_avatars,
    save_avatar,
    validate_avatar_content,
    validate_avatar_content_type,
)
from src.database.models import User
from src.database.schemas import AvatarResponse

avatar_router = APIRouter(prefix="/avatar", tags=["avatar"])


@avatar_router.get("", response_model=AvatarResponse, status_code=status.HTTP_200_OK)
async def get_my_avatar(request: Request, current_user: User = Depends(get_current_user)) -> AvatarResponse:
    return AvatarResponse(image_url=build_avatar_url(request, find_avatar_path(current_user.id)))


@avatar_router.post("", response_model=AvatarResponse, status_code=status.HTTP_200_OK)
async def upload_my_avatar(request: Request, image: UploadFile = File(...), current_user: User = Depends(get_current_user)) -> AvatarResponse:
    validate_avatar_content_type(image.content_type)
    content = await image.read()
    validate_avatar_content(content)
    png_content = convert_avatar_to_png(content)
    remove_existing_avatars(current_user.id)
    target_path = await save_avatar(current_user.id, png_content)

    return AvatarResponse(image_url=build_avatar_url(request, target_path))


@avatar_router.delete("", response_model=AvatarResponse, status_code=status.HTTP_200_OK)
async def delete_my_avatar(current_user: User = Depends(get_current_user)) -> AvatarResponse:
    remove_existing_avatars(current_user.id)
    return AvatarResponse(image_url=None)
