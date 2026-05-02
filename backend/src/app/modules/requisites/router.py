from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from src.app.modules.auth.dependencies import get_current_admin_user
from src.database import get_db
from src.database.crud import (
    create_requisite,
    delete_requisite,
    get_requisite_by_id,
    get_requisites,
    update_requisite,
)
from src.database.models import User
from src.database.schemas import RequisiteCreate, RequisiteRead, RequisiteUpdate

requisites_router = APIRouter(prefix="/requisites", tags=["requisites"])


@requisites_router.get("", response_model=list[RequisiteRead])
async def requisites_get(db: AsyncSession = Depends(get_db)) -> list[RequisiteRead]:
    return [RequisiteRead.model_validate(requisite) for requisite in await get_requisites(db)]


@requisites_router.post("", response_model=RequisiteRead, status_code=status.HTTP_201_CREATED)
async def requisites_create(
    data: RequisiteCreate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> RequisiteRead:
    return RequisiteRead.model_validate(await create_requisite(db, data))


@requisites_router.patch("/{requisite_id}", response_model=RequisiteRead)
async def requisites_patch(
    requisite_id: int,
    data: RequisiteUpdate,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> RequisiteRead:
    requisite = await get_requisite_by_id(db, requisite_id)
    if requisite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisite not found")
    return RequisiteRead.model_validate(await update_requisite(db, requisite, data))


@requisites_router.delete("/{requisite_id}", status_code=status.HTTP_204_NO_CONTENT)
async def requisites_delete(
    requisite_id: int,
    db: AsyncSession = Depends(get_db),
    _: User = Depends(get_current_admin_user),
) -> None:
    requisite = await get_requisite_by_id(db, requisite_id)
    if requisite is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Requisite not found")
    await delete_requisite(db, requisite)
