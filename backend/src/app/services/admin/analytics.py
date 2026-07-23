from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Literal

from fastapi import HTTPException
from sqlalchemy import case, func, select
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


def analytics_period(days: int) -> tuple[datetime, datetime]:
    if days < 7 or days > 365:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Analytics period must be between 7 and 365 days")
    end = ufa_now()
    return end - timedelta(days=days), end


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


async def sales_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    paid_filter = (Order.is_paid.is_(True), Order.is_canceled.is_(False), Order.created_at >= start)
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
    trend_rows = (await db.execute(select(
        func.date(Order.payment_paid_at).label("day"),
        func.coalesce(func.sum(Order.grand_total), 0).label("revenue"),
        func.count(Order.id).label("orders"),
    ).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.payment_paid_at.is_not(None),
        Order.payment_paid_at >= start,
    ).group_by(func.date(Order.payment_paid_at)).order_by(func.date(Order.payment_paid_at)))).all()
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
    }


async def products_summary(db: AsyncSession, *, days: int) -> dict[str, Any]:
    start, _ = analytics_period(days)
    top_rows = (await db.execute(select(
        OrderItem.product_id,
        OrderItem.product_name,
        OrderItem.product_sku,
        func.coalesce(func.sum(OrderItem.quantity), 0).label("quantity"),
        func.coalesce(func.sum(OrderItem.line_total), 0).label("revenue"),
    ).join(Order, Order.id == OrderItem.order_id).where(
        Order.is_paid.is_(True),
        Order.is_canceled.is_(False),
        Order.created_at >= start,
    ).group_by(OrderItem.product_id, OrderItem.product_name, OrderItem.product_sku).order_by(func.coalesce(func.sum(OrderItem.line_total), 0).desc()).limit(15))).all()
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
            {"product_id": int(product_id), "name": name, "sku": sku, "quantity": int(quantity), "revenue": money(revenue)}
            for product_id, name, sku, quantity, revenue in top_rows
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
        return csv_bytes(["user_id", "name", "email", "orders", "ltv"], ((row["user_id"], row["name"], row["email"], row["orders"], row["ltv"]) for row in data["top_customers"]))
    if section == "products":
        return csv_bytes(["product_id", "name", "sku", "quantity", "revenue"], ((row["product_id"], row["name"], row["sku"], row["quantity"], row["revenue"]) for row in data["top_products"]))
    if section == "discounts":
        return csv_bytes(["source", "applications", "discount_amount"], ((row["source"], row["applications"], row["discount_amount"]) for row in data["sources"]))
    return csv_bytes(["campaign_id", "name", "status", "goal", "audience", "sent", "failed", "clicked", "delivery_rate", "click_rate"], (
        (row["campaign_id"], row["name"], row["status"], row["goal"], row["audience"], row["sent"], row["failed"], row["clicked"], row["delivery_rate"], row["click_rate"])
        for row in data["campaigns"]
    ))
