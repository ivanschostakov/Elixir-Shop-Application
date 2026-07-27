from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import case, func, literal_column, select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette import status

from config import ufa_now
from src.database.models import (
    AdminPushCampaign,
    AdminPushCampaignRecipient,
    CustomerMarketingProfile,
    Order,
    OrderBenefitApplication,
    OrderDraft,
    OrderItem,
    Product,
    ReferralProfile,
    User,
    UserDevice,
    UserEvent,
    Variant,
)

AnalyticsSection = Literal["sales", "customers", "products", "discounts", "marketing"]
ANALYTICS_SECTIONS: tuple[AnalyticsSection, ...] = ("sales", "customers", "products", "discounts", "marketing")
ANALYTICS_TIMEZONE = "Asia/Yekaterinburg"


def analytics_period(days: int) -> tuple[datetime, datetime]:
    if days < 7 or days > 365:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Analytics period must be between 7 and 365 days")
    end = ufa_now()
    start = (end - timedelta(days=days - 1)).replace(
        hour=0,
        minute=0,
        second=0,
        microsecond=0,
    )
    return start, end


def percent(numerator: int | Decimal, denominator: int | Decimal) -> Decimal:
    if Decimal(denominator or 0) <= 0:
        return Decimal("0.00")
    return (Decimal(numerator or 0) * Decimal("100") / Decimal(denominator)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def money(value: Any) -> Decimal:
    return Decimal(value or 0).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def csv_bytes(headers: list[str], rows: Iterable[Iterable[Any]]) -> bytes:
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow([_csv_cell(value) for value in row])
    return output.getvalue().encode("utf-8-sig")


def _csv_cell(value: Any) -> str:
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(("=", "+", "-", "@")) else text


def _app_open_trend_query(*, start: datetime, granularity: Literal["daily", "monthly"]):
    # Keep timezone and date-trunc arguments as SQL literals. If SQLAlchemy emits
    # separate bind parameters for identical SELECT/GROUP BY expressions,
    # PostgreSQL no longer considers them the same expression and raises
    # GroupingError.
    timezone_name = literal_column(f"'{ANALYTICS_TIMEZONE}'")
    local_event_time = func.timezone(timezone_name, UserEvent.occurred_at)
    if granularity == "daily":
        period_expression = func.date(local_event_time)
    else:
        period_expression = func.date_trunc(literal_column("'month'"), local_event_time)
    period = period_expression.label("period")
    return (
        select(
            period,
            func.count(UserEvent.id).label("opens"),
            func.count(func.distinct(UserEvent.user_id)).label("customers"),
        )
        .where(UserEvent.event_name == "app_opened", UserEvent.occurred_at >= start)
        .group_by(period_expression)
        .order_by(period_expression)
    )


async def sales_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    paid_filter = (
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.payment_paid_at.is_not(None),
        Order.payment_paid_at >= start,
    )
    revenue, orders, units = (await db.execute(select(
        func.coalesce(func.sum(Order.grand_total), 0),
        func.count(Order.id),
        func.coalesce(func.sum(Order.total_quantity), 0),
    ).where(*paid_filter))).one()
    customers = int((await db.execute(select(func.count(func.distinct(Order.user_id))).where(*paid_filter))).scalar_one())
    repeat_customers = int((await db.execute(select(func.count()).select_from(
        select(Order.user_id)
        .where(*paid_filter)
        .group_by(Order.user_id)
        .having(func.count(Order.id) > 1)
        .subquery()
    ))).scalar_one())
    revenue_decimal = money(revenue)
    orders_count = int(orders or 0)
    local_payment_time = func.timezone(ANALYTICS_TIMEZONE, Order.payment_paid_at)
    trend_rows = (await db.execute(select(
        func.date(local_payment_time).label("day"),
        func.coalesce(func.sum(Order.grand_total), 0).label("revenue"),
        func.count(Order.id).label("orders"),
    ).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.payment_paid_at.is_not(None),
        Order.payment_paid_at >= start,
    ).group_by(func.date(local_payment_time)).order_by(func.date(local_payment_time)))).all()
    status_rows = (await db.execute(select(Order.payment_status, func.count(Order.id)).where(Order.created_at >= start).group_by(Order.payment_status))).all()
    return {
        "summary": {
            "revenue": revenue_decimal,
            "paid_orders": orders_count,
            "units_sold": int(units or 0),
            "average_order_value": money(revenue_decimal / orders_count) if orders_count else Decimal("0.00"),
            "customers": customers,
            "repeat_customers": repeat_customers,
            "repeat_rate": percent(repeat_customers, customers),
        },
        "trend": [{"date": row.day, "revenue": money(row.revenue), "orders": int(row.orders)} for row in trend_rows],
        "payment_statuses": [{"status": str(status_name or "unknown"), "count": int(count)} for status_name, count in status_rows],
    }


async def customers_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, end = analytics_period(days)
    total_customers = int((await db.execute(select(func.count(User.id)))).scalar_one())
    new_customers = int((await db.execute(select(func.count(User.id)).where(User.created_at >= start))).scalar_one())
    active_customers = int((await db.execute(select(func.count(User.id)).where(User.last_active_at >= start))).scalar_one())
    inactive_customers = int((await db.execute(select(func.count(User.id)).where((User.last_active_at.is_(None)) | (User.last_active_at < end - timedelta(days=30))))).scalar_one())
    abandoned_carts = int((await db.execute(select(func.count(OrderDraft.id)).where(OrderDraft.status == "draft", OrderDraft.items_count > 0, OrderDraft.updated_at >= start))).scalar_one())
    ltv_rows = (await db.execute(select(
        User.id,
        User.name,
        User.surname,
        User.email,
        func.count(Order.id).label("orders"),
        func.coalesce(func.sum(Order.grand_total), 0).label("ltv"),
    ).join(Order, Order.user_id == User.id).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
    ).group_by(User.id).order_by(func.coalesce(func.sum(Order.grand_total), 0).desc()).limit(10))).all()
    band_rows = (await db.execute(select(
        case(
            (User.created_at >= start, "new"),
            (User.last_active_at >= start, "active"),
            else_="inactive",
        ).label("band"),
        func.count(User.id),
    ).group_by("band"))).all()
    platform_rows = (await db.execute(select(
        UserDevice.platform,
        func.count(func.distinct(UserDevice.user_id)),
    ).where(
        UserDevice.is_active.is_(True),
        UserDevice.last_seen_at >= start,
    ).group_by(UserDevice.platform).order_by(func.count(func.distinct(UserDevice.user_id)).desc()))).all()
    app_version_rows = (await db.execute(select(
        UserDevice.platform,
        UserDevice.app_version,
        func.count(func.distinct(UserDevice.user_id)),
    ).where(
        UserDevice.is_active.is_(True),
        UserDevice.last_seen_at >= start,
        UserDevice.app_version.is_not(None),
    ).group_by(UserDevice.platform, UserDevice.app_version).order_by(func.count(func.distinct(UserDevice.user_id)).desc()).limit(20))).all()
    push_permission_rows = (await db.execute(select(
        CustomerMarketingProfile.push_permission,
        func.count(CustomerMarketingProfile.user_id),
    ).where(
        CustomerMarketingProfile.last_seen_at >= start,
    ).group_by(CustomerMarketingProfile.push_permission).order_by(func.count(CustomerMarketingProfile.user_id).desc()))).all()
    event_rows = (await db.execute(select(
        UserEvent.event_name,
        func.count(UserEvent.id),
        func.count(func.distinct(UserEvent.user_id)),
    ).where(
        UserEvent.occurred_at >= start,
    ).group_by(UserEvent.event_name).order_by(func.count(UserEvent.id).desc()))).all()
    app_open_filter = (UserEvent.event_name == "app_opened", UserEvent.occurred_at >= start)
    app_opens_total, app_open_users = (await db.execute(select(
        func.count(UserEvent.id),
        func.count(func.distinct(UserEvent.user_id)),
    ).where(*app_open_filter))).one()
    app_open_daily_rows = (await db.execute(_app_open_trend_query(start=start, granularity="daily"))).all()
    app_open_monthly_rows = (await db.execute(_app_open_trend_query(start=start, granularity="monthly"))).all()
    return {
        "summary": {
            "total_customers": total_customers,
            "new_customers": new_customers,
            "active_customers": active_customers,
            "inactive_customers": inactive_customers,
            "abandoned_carts": abandoned_carts,
            "activation_rate": percent(active_customers, total_customers),
        },
        "top_customers": [
            {
                "user_id": int(user_id),
                "name": f"{name} {surname}".strip() or f"User {user_id}",
                "email": email,
                "orders": int(orders),
                "ltv": money(ltv),
            }
            for user_id, name, surname, email, orders, ltv in ltv_rows
        ],
        "segments": [{"name": str(band), "count": int(count)} for band, count in band_rows],
        "devices": {
            "platforms": [{"platform": str(platform), "customers": int(count)} for platform, count in platform_rows],
            "app_versions": [
                {"platform": str(platform), "app_version": str(app_version), "customers": int(count)}
                for platform, app_version, count in app_version_rows
            ],
            "push_permissions": [
                {"permission": str(permission), "customers": int(count)}
                for permission, count in push_permission_rows
            ],
        },
        "events": [
            {"event_name": str(event_name), "events": int(events), "customers": int(customers)}
            for event_name, events, customers in event_rows
        ],
        "app_opens": {
            "total": int(app_opens_total or 0),
            "unique_customers": int(app_open_users or 0),
            "average_per_customer": (
                (Decimal(app_opens_total or 0) / Decimal(app_open_users)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
                if app_open_users
                else Decimal("0.00")
            ),
            "daily": [
                {"period": row.period, "opens": int(row.opens), "customers": int(row.customers)}
                for row in app_open_daily_rows
            ],
            "monthly": [
                {"period": row.period, "opens": int(row.opens), "customers": int(row.customers)}
                for row in app_open_monthly_rows
            ],
        },
    }


async def products_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    top_rows = (await db.execute(select(
        OrderItem.product_id,
        OrderItem.product_name,
        OrderItem.product_sku,
        func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
        func.coalesce(func.sum(OrderItem.line_total), 0).label("revenue"),
        func.count(func.distinct(OrderItem.order_id)).label("orders"),
        func.count(func.distinct(Order.user_id)).label("customers"),
    ).join(Order, Order.id == OrderItem.order_id).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.payment_paid_at.is_not(None),
        Order.payment_paid_at >= start,
    ).group_by(OrderItem.product_id, OrderItem.product_name, OrderItem.product_sku).order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc()).limit(15))).all()
    top_product_ids = [int(row.product_id) for row in top_rows]
    view_rows = (await db.execute(select(
        UserEvent.entity_id,
        func.count(UserEvent.id).label("views"),
        func.count(func.distinct(UserEvent.user_id)).label("viewers"),
    ).where(
        UserEvent.event_name == "product_viewed",
        UserEvent.entity_type == "product",
        UserEvent.entity_id.in_(top_product_ids),
        UserEvent.occurred_at >= start,
    ).group_by(UserEvent.entity_id))).all() if top_product_ids else []
    stock_rows = (await db.execute(select(
        Variant.product_id,
        func.coalesce(func.sum(Variant.stock), 0).label("stock"),
    ).where(
        Variant.product_id.in_(top_product_ids),
        Variant.archived.is_(False),
    ).group_by(Variant.product_id))).all() if top_product_ids else []
    views_by_product = {int(row.entity_id): (int(row.views), int(row.viewers)) for row in view_rows}
    stock_by_product = {int(row.product_id): int(row.stock) for row in stock_rows}
    low_stock_rows = (await db.execute(select(
        Product.id,
        Product.name,
        Product.sku,
        func.coalesce(func.sum(Variant.stock), 0).label("stock"),
    ).join(Variant, Variant.product_id == Product.id).where(
        Product.archived.is_(False),
        Variant.archived.is_(False),
    ).group_by(Product.id).having(func.coalesce(func.sum(Variant.stock), 0) <= 5).order_by(func.coalesce(func.sum(Variant.stock), 0).asc(), Product.name).limit(15))).all()
    active_products = int((await db.execute(select(func.count(Product.id)).where(Product.archived.is_(False)))).scalar_one())
    in_stock_products = int((await db.execute(select(func.count(Product.id)).where(Product.archived.is_(False), Product.in_stock.is_(True)))).scalar_one())
    return {
        "summary": {
            "active_products": active_products,
            "in_stock_products": in_stock_products,
            "stock_coverage_rate": percent(in_stock_products, active_products),
            "low_stock_products": len(low_stock_rows),
        },
        "top_products": [
            {
                "product_id": int(product_id),
                "name": name,
                "sku": sku,
                "quantity": int(quantity),
                "revenue": money(revenue),
                "orders": int(orders),
                "customers": int(customers),
                "views": views_by_product.get(int(product_id), (0, 0))[0],
                "viewers": views_by_product.get(int(product_id), (0, 0))[1],
                "conversion_rate": percent(int(customers), views_by_product.get(int(product_id), (0, 0))[1]),
                "stock": stock_by_product.get(int(product_id), 0),
            }
            for product_id, name, sku, quantity, revenue, orders, customers in top_rows
        ],
        "low_stock": [
            {"product_id": int(product_id), "name": name, "sku": sku, "stock": int(stock)}
            for product_id, name, sku, stock in low_stock_rows
        ],
    }


async def discounts_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    total_discount, applications = (await db.execute(select(
        func.coalesce(func.sum(OrderBenefitApplication.discount_amount), 0),
        func.count(OrderBenefitApplication.id),
    ).where(OrderBenefitApplication.created_at >= start, OrderBenefitApplication.status == "applied"))).one()
    source_rows = (await db.execute(select(
        OrderBenefitApplication.source_kind,
        func.count(OrderBenefitApplication.id),
        func.coalesce(func.sum(OrderBenefitApplication.discount_amount), 0),
    ).where(
        OrderBenefitApplication.created_at >= start,
        OrderBenefitApplication.status == "applied",
    ).group_by(OrderBenefitApplication.source_kind).order_by(func.coalesce(func.sum(OrderBenefitApplication.discount_amount), 0).desc()))).all()
    referral_profiles = int((await db.execute(select(func.count(ReferralProfile.id)))).scalar_one())
    active_referrals = int((await db.execute(select(func.count(ReferralProfile.id)).where(ReferralProfile.referral_discount_base_total > 0))).scalar_one())
    return {
        "summary": {
            "total_discount": money(total_discount),
            "applications": int(applications or 0),
            "referral_profiles": referral_profiles,
            "active_referrals": active_referrals,
            "active_referral_rate": percent(active_referrals, referral_profiles),
        },
        "sources": [
            {"source": str(source), "applications": int(count), "discount_amount": money(amount)}
            for source, count, amount in source_rows
        ],
    }


async def marketing_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    campaigns = list((await db.execute(select(AdminPushCampaign).where(AdminPushCampaign.created_at >= start).order_by(AdminPushCampaign.created_at.desc()).limit(20))).scalars().all())
    sent = sum(row.sent_count for row in campaigns)
    audience = sum(row.audience_count for row in campaigns)
    failed = sum(row.failed_count for row in campaigns)
    clicked_rows = (await db.execute(select(
        AdminPushCampaignRecipient.campaign_id,
        func.count(AdminPushCampaignRecipient.id),
    ).where(
        AdminPushCampaignRecipient.clicked_at.is_not(None),
        AdminPushCampaignRecipient.created_at >= start,
    ).group_by(AdminPushCampaignRecipient.campaign_id))).all()
    clicked_by_campaign = {int(campaign_id): int(count) for campaign_id, count in clicked_rows}
    clicked = sum(clicked_by_campaign.values())
    return {
        "summary": {
            "campaigns": len(campaigns),
            "audience": audience,
            "sent": sent,
            "failed": failed,
            "clicked": clicked,
            "delivery_rate": percent(sent, audience),
            "click_rate": percent(clicked, sent),
            "failure_rate": percent(failed, audience),
        },
        "campaigns": [
            {
                "campaign_id": row.id,
                "name": row.name,
                "status": row.status,
                "goal": row.goal,
                "audience": row.audience_count,
                "sent": row.sent_count,
                "failed": row.failed_count,
                "clicked": clicked_by_campaign.get(row.id, 0),
                "delivery_rate": percent(row.sent_count, row.audience_count),
                "click_rate": percent(clicked_by_campaign.get(row.id, 0), row.sent_count),
                "created_at": row.created_at,
            }
            for row in campaigns
        ],
    }


async def analytics_snapshot(db: AsyncSession, *, days: int) -> dict[str, Any]:
    return {
        "days": days,
        "generated_at": ufa_now(),
        "sales": await sales_summary(db, days=days),
        "customers": await customers_summary(db, days=days),
        "products": await products_summary(db, days=days),
        "discounts": await discounts_summary(db, days=days),
        "marketing": await marketing_summary(db, days=days),
    }


def analytics_csv(section: AnalyticsSection, snapshot: dict[str, Any]) -> bytes:
    if section not in ANALYTICS_SECTIONS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unknown analytics report")
    data = snapshot[section]
    if section == "sales":
        return csv_bytes(["date", "revenue", "orders"], ((row["date"], row["revenue"], row["orders"]) for row in data["trend"]))
    if section == "customers":
        return csv_bytes(
            ["period", "opens", "unique_customers"],
            ((row["period"], row["opens"], row["customers"]) for row in data["app_opens"]["daily"]),
        )
    if section == "products":
        return csv_bytes(
            ["product_id", "name", "sku", "quantity", "revenue", "orders", "customers", "views", "viewers", "conversion_rate", "stock"],
            (
                (
                    row["product_id"],
                    row["name"],
                    row["sku"],
                    row["quantity"],
                    row["revenue"],
                    row["orders"],
                    row["customers"],
                    row["views"],
                    row["viewers"],
                    row["conversion_rate"],
                    row["stock"],
                )
                for row in data["top_products"]
            ),
        )
    if section == "discounts":
        return csv_bytes(["source", "applications", "discount_amount"], ((row["source"], row["applications"], row["discount_amount"]) for row in data["sources"]))
    return csv_bytes(["campaign_id", "name", "status", "goal", "audience", "sent", "failed", "clicked", "delivery_rate", "click_rate"], (
        (row["campaign_id"], row["name"], row["status"], row["goal"], row["audience"], row["sent"], row["failed"], row["clicked"], row["delivery_rate"], row["click_rate"])
        for row in data["campaigns"]
    ))
