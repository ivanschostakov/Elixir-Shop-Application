from fastapi import Depends, HTTPException, Query, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload
from starlette import status
from src.app.modules.admin.helpers import ensure_not_stale, serialize_business_content, serialize_business_content_version
from src.app.modules.admin.schemas import AdminBusinessContentRead, AdminBusinessContentUpdatePayload, AdminBusinessContentVersionRead, AdminPage
from src.app.services.admin import AdminContext, add_admin_audit, require_permission
from src.database import get_db
from src.database.models import Admin, BusinessContentPage, BusinessContentVersion
from .common import admin_content_router


@admin_content_router.get("/business-content", response_model=AdminPage[AdminBusinessContentRead])
async def list_business_content(content_status: str | None = Query(default=None, alias="status", pattern="^(draft|published|archived)$"), limit: int = Query(default=50, ge=1, le=200), offset: int = Query(default=0, ge=0), db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("banners.manage")),) -> AdminPage[AdminBusinessContentRead]:
    filters = [BusinessContentPage.status == content_status] if content_status else []
    total = int((await db.execute(select(func.count(BusinessContentPage.id)).where(*filters))).scalar_one())
    rows = list((await db.execute(select(BusinessContentPage).options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user)).where(*filters).order_by(BusinessContentPage.code.asc()).offset(offset).limit(limit))).scalars().all())
    return AdminPage(items=[serialize_business_content(row) for row in rows], total=total, limit=limit, offset=offset)


@admin_content_router.put("/business-content/{code}", response_model=AdminBusinessContentRead)
async def update_business_content(code: str, payload: AdminBusinessContentUpdatePayload, request: Request, db: AsyncSession = Depends(get_db), context: AdminContext = Depends(require_permission("banners.manage", write=True)),) -> AdminBusinessContentRead:
    page = (await db.execute(select(BusinessContentPage).options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user)).where(BusinessContentPage.code == code).execution_options(populate_existing=True))).scalar_one_or_none()
    if page is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business content page not found")
    ensure_not_stale(actual=page.updated_at, expected=payload.expected_updated_at)
    before = serialize_business_content(page).model_dump(mode="json")
    page.version += 1
    page.title_ru = payload.title_ru
    page.title_en = payload.title_en
    page.body_ru = payload.body_ru
    page.body_en = payload.body_en
    page.link_url = payload.link_url
    page.status = payload.status
    page.metadata_json = payload.metadata_json
    page.updated_by_user_id = context.user.id
    db.add(BusinessContentVersion(page_id=page.id, version=page.version, actor_user_id=context.user.id, snapshot_json={"code": page.code, "title_ru": page.title_ru, "title_en": page.title_en, "body_ru": page.body_ru, "body_en": page.body_en, "link_url": page.link_url, "status": page.status, "metadata_json": page.metadata_json,},))
    await db.flush()
    page = (await db.execute(select(BusinessContentPage).options(joinedload(BusinessContentPage.updated_by).joinedload(Admin.user)).where(BusinessContentPage.id == page.id).execution_options(populate_existing=True))).scalar_one()
    result = serialize_business_content(page)
    await add_admin_audit(db, request, context, action="business_content.update", entity_type="business_content", entity_id=page.code, before=before, after=result.model_dump(mode="json"))
    await db.commit()
    return result


@admin_content_router.get("/business-content/{code}/versions", response_model=list[AdminBusinessContentVersionRead])
async def business_content_versions(code: str, db: AsyncSession = Depends(get_db), _: AdminContext = Depends(require_permission("banners.manage")),) -> list[AdminBusinessContentVersionRead]:
    page_id = (await db.execute(select(BusinessContentPage.id).where(BusinessContentPage.code == code))).scalar_one_or_none()
    if page_id is None: raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Business content page not found")
    rows = list((await db.execute(select(BusinessContentVersion).options(joinedload(BusinessContentVersion.actor).joinedload(Admin.user)).where(BusinessContentVersion.page_id == page_id).order_by(BusinessContentVersion.version.desc(), BusinessContentVersion.id.desc()))).scalars().all())
    return [serialize_business_content_version(row) for row in rows]
