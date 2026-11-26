from datetime import date
from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.modules.admin.schemas import AdminAnalyticsResponse
from src.app.services.admin import AdminContext, require_permission
from src.app.services.admin.analytics import ANALYTICS_SECTIONS, AnalyticsSection, analytics_csv, analytics_snapshot
from src.database import get_db

admin_analytics_router = APIRouter(prefix="/analytics", tags=["admin_analytics"])


@admin_analytics_router.get("", response_model=AdminAnalyticsResponse)
async def get_analytics(
    days: int = Query(default=30, ge=7, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("analytics.read")),
) -> AdminAnalyticsResponse:
    return AdminAnalyticsResponse.model_validate(await analytics_snapshot(db, days=days, date_from=date_from, date_to=date_to))


@admin_analytics_router.get("/{section}.csv")
async def download_analytics_csv(
    section: AnalyticsSection,
    days: int = Query(default=30, ge=7, le=365),
    date_from: date | None = None,
    date_to: date | None = None,
    db: AsyncSession = Depends(get_db),
    _: AdminContext = Depends(require_permission("analytics.read")),
) -> StreamingResponse:
    snapshot = await analytics_snapshot(db, days=days, date_from=date_from, date_to=date_to)
    period = f"{date_from}_{date_to}" if date_from else f"{days}d"
    content = analytics_csv(section, snapshot)
    return StreamingResponse(
        iter([content]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="analytics-{section}-{period}.csv"'},
    )


__all__ = ["admin_analytics_router", "ANALYTICS_SECTIONS"]
