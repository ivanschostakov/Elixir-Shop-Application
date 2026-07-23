from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator
from sqlalchemy import Select, and_, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from config import ufa_now
from src.database.models import (
    AdminCustomerSegment,
    AdminCustomerSegmentSnapshotItem,
    AdminPushCampaign,
    AdminPushCampaignRecipient,
    BasketItem,
    CustomerAttribution,
    CustomerMarketingProfile,
    DeliveryAddress,
    FavouredProduct,
    Order,
    ProductByCategory,
    ReferralProfile,
    Review,
    User,
    UserDevice,
    UserEvent,
    UserCategoryRecommendationSignal,
    UserProductRecommendationSignal,
    UserPushToken,
)


MAX_CAMPAIGN_AUDIENCE = 50_000
MAX_SEGMENT_PREVIEW = 50
MAX_SEGMENT_EXPORT = 20_000

SegmentOperator = Literal[
    "eq",
    "neq",
    "gte",
    "lte",
    "before",
    "after",
    "contains",
    "in",
    "exists",
]
SegmentCombinator = Literal["and", "or"]

SUPPORTED_FIELDS = frozenset((
    "registration_date",
    "last_activity",
    "inactive_days",
    "customer_type",
    "order_count",
    "paid_order_count",
    "ltv",
    "average_order_value",
    "last_purchase",
    "abandoned_basket",
    "favorite_category",
    "product_views",
    "product_viewed",
    "cart_activity",
    "review_rating",
    "city",
    "region",
    "referral_status",
    "push_available",
    "campaign_participation",
    "platform",
    "app_version",
    "push_permission",
    "install_source",
    "lifecycle_stage",
    "lead_score",
    "event_count",
    "event_name",
    "is_active",
    "is_verified",
    "q",
))


class SegmentCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field: str
    operator: SegmentOperator
    value: Any = None

    @field_validator("field")
    @classmethod
    def _field_is_supported(cls, value: str) -> str:
        if value not in SUPPORTED_FIELDS:
            raise ValueError(f"Unsupported segment field: {value}")
        return value


class SegmentGroup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    combinator: SegmentCombinator = "and"
    conditions: list[Any] = Field(default_factory=list, max_length=40)


class SegmentDefinition(SegmentGroup):
    version: Literal[2] = 2
    exclusions: list[int] = Field(default_factory=list, max_length=20)


class LegacySegmentFilters(BaseModel):
    model_config = ConfigDict(extra="forbid")

    q: str | None = Field(default=None, max_length=100)
    is_active: bool | None = None
    is_verified: bool | None = None
    has_push_token: bool | None = None
    min_orders: int | None = Field(default=None, ge=0, le=100_000)
    min_paid_total: Decimal | None = Field(default=None, ge=0)
    last_order_before: datetime | None = None
    last_order_after: datetime | None = None
    last_active_before: datetime | None = None
    last_active_after: datetime | None = None


def _condition(field: str, operator: SegmentOperator, value: Any = None) -> dict[str, Any]:
    return {"field": field, "operator": operator, "value": value}


def _legacy_to_definition(raw: dict[str, Any]) -> dict[str, Any]:
    filters = LegacySegmentFilters.model_validate(raw)
    conditions: list[dict[str, Any]] = []
    if filters.q:
        conditions.append(_condition("q", "contains", filters.q))
    if filters.is_active is not None:
        conditions.append(_condition("is_active", "eq", filters.is_active))
    if filters.is_verified is not None:
        conditions.append(_condition("is_verified", "eq", filters.is_verified))
    if filters.has_push_token is not None:
        conditions.append(_condition("push_available", "eq", filters.has_push_token))
    if filters.min_orders is not None:
        conditions.append(_condition("order_count", "gte", filters.min_orders))
    if filters.min_paid_total is not None:
        conditions.append(_condition("ltv", "gte", str(filters.min_paid_total)))
    if filters.last_order_before is not None:
        conditions.append(_condition("last_purchase", "before", filters.last_order_before.isoformat()))
    if filters.last_order_after is not None:
        conditions.append(_condition("last_purchase", "after", filters.last_order_after.isoformat()))
    if filters.last_active_before is not None:
        conditions.append(_condition("last_activity", "before", filters.last_active_before.isoformat()))
    if filters.last_active_after is not None:
        conditions.append(_condition("last_activity", "after", filters.last_active_after.isoformat()))
    return {"version": 2, "combinator": "and", "conditions": conditions, "exclusions": []}


def _validate_group_payload(group: dict[str, Any]) -> None:
    for raw_item in group.get("conditions") or []:
        if isinstance(raw_item, dict) and "field" in raw_item:
            SegmentCondition.model_validate(raw_item)
        elif isinstance(raw_item, dict):
            nested = SegmentGroup.model_validate(raw_item)
            _validate_group_payload(nested.model_dump())
        else:
            raise ValueError("Segment condition must be an object")


def normalize_segment_filters(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("version") == 2 or "conditions" in raw:
        definition = SegmentDefinition.model_validate(raw).model_dump(mode="json")
    else:
        definition = SegmentDefinition.model_validate(_legacy_to_definition(raw)).model_dump(mode="json")
    _validate_group_payload(definition)
    return definition


def _orders_aggregate():
    return select(
        Order.user_id.label("user_id"),
        func.count(Order.id).label("orders_count"),
        func.count(Order.id).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)).label("paid_orders_count"),
        func.coalesce(
            func.sum(Order.grand_total).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)),
            0,
        ).label("paid_total"),
        func.coalesce(
            func.avg(Order.grand_total).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)),
            0,
        ).label("average_order_value"),
        func.min(Order.created_at).label("first_order_at"),
        func.max(Order.created_at).label("last_order_at"),
        func.max(Order.created_at).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)).label("last_purchase_at"),
    ).group_by(Order.user_id).subquery()


def _review_aggregate():
    return select(
        Review.user_id.label("user_id"),
        func.avg(Review.value).filter(Review.moderated.is_(True), Review.rejected_at.is_(None)).label("review_rating"),
        func.count(Review.id).label("reviews_count"),
    ).where(Review.user_id.is_not(None)).group_by(Review.user_id).subquery()


def _product_signal_aggregate():
    return select(
        UserProductRecommendationSignal.user_id.label("user_id"),
        func.coalesce(func.sum(UserProductRecommendationSignal.view_count), 0).label("product_views"),
        func.coalesce(func.sum(UserProductRecommendationSignal.cart_quantity), 0).label("cart_activity"),
        func.max(UserProductRecommendationSignal.last_viewed_at).label("last_product_viewed_at"),
        func.max(UserProductRecommendationSignal.last_carted_at).label("last_carted_at"),
    ).group_by(UserProductRecommendationSignal.user_id).subquery()


def _basket_activity_aggregate():
    return select(
        BasketItem.user_id.label("user_id"),
        func.coalesce(func.sum(BasketItem.quantity), 0).label("basket_quantity"),
        func.max(BasketItem.updated_at).label("last_basket_at"),
    ).group_by(BasketItem.user_id).subquery()


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    raise ValueError("Expected ISO datetime")


def _parse_decimal(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        raise ValueError("Expected numeric value") from None


def _parse_int(value: Any) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError):
        raise ValueError("Expected integer value") from None
    return result


def _parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str) and value.lower() in {"true", "false"}:
        return value.lower() == "true"
    raise ValueError("Expected boolean value")


def _parse_int_list(value: Any) -> list[int]:
    if isinstance(value, list):
        values = value
    else:
        values = [value]
    result = [_parse_int(item) for item in values]
    if any(item <= 0 for item in result):
        raise ValueError("IDs must be positive")
    return list(dict.fromkeys(result))


def _comparison(column, operator: str, value: Any):
    if operator == "eq":
        return column == value
    if operator == "neq":
        return column != value
    if operator == "gte":
        return column >= value
    if operator == "lte":
        return column <= value
    if operator == "before":
        return column <= value
    if operator == "after":
        return column >= value
    raise ValueError(f"Unsupported operator for comparison: {operator}")


def _condition_clause(condition: SegmentCondition, *, aggregate, review_aggregate, product_signal_aggregate, basket_aggregate):
    field = condition.field
    operator = condition.operator
    value = condition.value

    if field == "q":
        if operator != "contains":
            raise ValueError("Search supports only contains")
        pattern = f"%{str(value or '').strip()}%"
        return or_(User.name.ilike(pattern), User.surname.ilike(pattern), User.email.ilike(pattern), User.phone_number.ilike(pattern), User.telegram_username.ilike(pattern))
    if field == "is_active":
        return User.is_active.is_(_parse_bool(value))
    if field == "is_verified":
        return User.is_verified.is_(_parse_bool(value))
    if field == "registration_date":
        return _comparison(User.created_at, operator, _parse_datetime(value))
    if field == "last_activity":
        return _comparison(User.last_active_at, operator, _parse_datetime(value))
    if field == "inactive_days":
        return User.last_active_at <= ufa_now() - timedelta(days=max(_parse_int(value), 0))
    if field == "customer_type":
        orders = func.coalesce(aggregate.c.orders_count, 0)
        if value == "first_time":
            return orders <= 1
        if value == "repeat":
            return orders >= 2
        if value == "no_orders":
            return orders == 0
        raise ValueError("Unsupported customer_type")
    if field == "order_count":
        return _comparison(func.coalesce(aggregate.c.orders_count, 0), operator, _parse_int(value))
    if field == "paid_order_count":
        return _comparison(func.coalesce(aggregate.c.paid_orders_count, 0), operator, _parse_int(value))
    if field == "ltv":
        return _comparison(func.coalesce(aggregate.c.paid_total, 0), operator, _parse_decimal(value))
    if field == "average_order_value":
        return _comparison(func.coalesce(aggregate.c.average_order_value, 0), operator, _parse_decimal(value))
    if field == "last_purchase":
        return _comparison(aggregate.c.last_purchase_at, operator, _parse_datetime(value))
    if field == "abandoned_basket":
        has_basket = func.coalesce(basket_aggregate.c.basket_quantity, 0) > 0
        no_later_order = or_(aggregate.c.last_order_at.is_(None), basket_aggregate.c.last_basket_at > aggregate.c.last_order_at)
        clause = and_(has_basket, no_later_order)
        return clause if _parse_bool(value) else ~clause
    if field == "favorite_category":
        category_ids = _parse_int_list(value)
        product_ids = select(ProductByCategory.product_id).where(ProductByCategory.category_id.in_(category_ids))
        clause = exists(select(FavouredProduct.id).where(FavouredProduct.user_id == User.id, FavouredProduct.product_id.in_(product_ids)))
        return clause if operator != "neq" else ~clause
    if field == "product_views":
        return _comparison(func.coalesce(product_signal_aggregate.c.product_views, 0), operator, _parse_int(value))
    if field == "product_viewed":
        product_ids = _parse_int_list(value)
        clause = exists(select(UserProductRecommendationSignal.id).where(
            UserProductRecommendationSignal.user_id == User.id,
            UserProductRecommendationSignal.product_id.in_(product_ids),
            UserProductRecommendationSignal.view_count > 0,
        ))
        return clause if operator != "neq" else ~clause
    if field == "cart_activity":
        return _comparison(func.coalesce(product_signal_aggregate.c.cart_activity, 0) + func.coalesce(basket_aggregate.c.basket_quantity, 0), operator, _parse_int(value))
    if field == "review_rating":
        return _comparison(func.coalesce(review_aggregate.c.review_rating, 0), operator, _parse_decimal(value))
    if field == "city":
        if operator != "contains":
            raise ValueError("City supports only contains")
        pattern = f"%{str(value or '').strip()}%"
        return exists(select(DeliveryAddress.id).where(DeliveryAddress.user_id == User.id, DeliveryAddress.city.ilike(pattern)))
    if field == "region":
        if operator != "contains":
            raise ValueError("Region supports only contains")
        pattern = f"%{str(value or '').strip()}%"
        return exists(select(DeliveryAddress.id).where(
            DeliveryAddress.user_id == User.id,
            or_(DeliveryAddress.full_address.ilike(pattern), DeliveryAddress.details.ilike(pattern), DeliveryAddress.city.ilike(pattern)),
        ))
    if field == "referral_status":
        has_referral = exists(select(ReferralProfile.id).where(ReferralProfile.user_id == User.id))
        active_discount = exists(select(ReferralProfile.id).where(ReferralProfile.user_id == User.id, ReferralProfile.current_discount_percent > 0))
        if value == "has_referral":
            return has_referral
        if value == "no_referral":
            return ~has_referral
        if value == "discount_active":
            return active_discount
        raise ValueError("Unsupported referral_status")
    if field == "push_available":
        push_exists = exists(select(UserPushToken.id).where(UserPushToken.user_id == User.id))
        return push_exists if _parse_bool(value) else ~push_exists
    if field == "platform":
        platform_exists = exists(select(UserDevice.id).where(
            UserDevice.user_id == User.id,
            UserDevice.platform == str(value).strip().lower(),
            UserDevice.is_active.is_(True),
        ))
        return ~platform_exists if operator == "neq" else platform_exists
    if field == "app_version":
        normalized = str(value or "").strip()
        if operator == "contains":
            version_clause = UserDevice.app_version.ilike(f"%{normalized}%")
        elif operator == "neq":
            version_clause = UserDevice.app_version != normalized
        elif operator == "eq":
            version_clause = UserDevice.app_version == normalized
        else:
            raise ValueError("App version supports eq, neq and contains")
        return exists(select(UserDevice.id).where(
            UserDevice.user_id == User.id,
            UserDevice.is_active.is_(True),
            version_clause,
        ))
    if field == "push_permission":
        normalized = str(value or "").strip().lower()
        clause = func.coalesce(CustomerMarketingProfile.push_permission, "unknown") == normalized
        return ~clause if operator == "neq" else clause
    if field == "install_source":
        normalized = str(value or "").strip()
        if operator == "contains":
            source_clause = CustomerAttribution.install_source.ilike(f"%{normalized}%")
        elif operator == "neq":
            source_clause = CustomerAttribution.install_source != normalized
        elif operator == "eq":
            source_clause = CustomerAttribution.install_source == normalized
        else:
            raise ValueError("Install source supports eq, neq and contains")
        return exists(select(CustomerAttribution.user_id).where(
            CustomerAttribution.user_id == User.id,
            source_clause,
        ))
    if field == "lifecycle_stage":
        normalized = str(value or "").strip().lower()
        clause = func.coalesce(CustomerMarketingProfile.lifecycle_stage, "new") == normalized
        return ~clause if operator == "neq" else clause
    if field == "lead_score":
        return _comparison(func.coalesce(CustomerMarketingProfile.lead_score, 0), operator, _parse_int(value))
    if field == "event_count":
        return _comparison(func.coalesce(CustomerMarketingProfile.total_events, 0), operator, _parse_int(value))
    if field == "event_name":
        normalized = str(value or "").strip()
        event_exists = exists(select(UserEvent.id).where(
            UserEvent.user_id == User.id,
            UserEvent.event_name == normalized,
        ))
        return ~event_exists if operator == "neq" else event_exists
    if field == "campaign_participation":
        if isinstance(value, dict):
            campaign_id = value.get("campaign_id")
            recipient_status = value.get("status")
        else:
            campaign_id = value
            recipient_status = None
        campaign_clause = exists(select(AdminPushCampaignRecipient.id).join(AdminPushCampaign, AdminPushCampaign.id == AdminPushCampaignRecipient.campaign_id).where(
            AdminPushCampaignRecipient.user_id == User.id,
            AdminPushCampaign.id == _parse_int(campaign_id),
            *([AdminPushCampaignRecipient.status == str(recipient_status)] if recipient_status else []),
        ))
        return campaign_clause if operator != "neq" else ~campaign_clause
    raise ValueError(f"Unsupported segment field: {field}")


def _group_clause(group: SegmentGroup, *, aggregate, review_aggregate, product_signal_aggregate, basket_aggregate):
    clauses = []
    for raw_item in group.conditions:
        if isinstance(raw_item, SegmentCondition):
            item = raw_item
        elif isinstance(raw_item, dict) and "field" in raw_item:
            item = SegmentCondition.model_validate(raw_item)
        else:
            item = None
        if item is not None:
            clauses.append(_condition_clause(
                item,
                aggregate=aggregate,
                review_aggregate=review_aggregate,
                product_signal_aggregate=product_signal_aggregate,
                basket_aggregate=basket_aggregate,
            ))
        else:
            nested_group = raw_item if isinstance(raw_item, SegmentGroup) else SegmentGroup.model_validate(raw_item)
            nested = _group_clause(
                nested_group,
                aggregate=aggregate,
                review_aggregate=review_aggregate,
                product_signal_aggregate=product_signal_aggregate,
                basket_aggregate=basket_aggregate,
            )
            if nested is not None:
                clauses.append(nested)
    if not clauses:
        return None
    return and_(*clauses) if group.combinator == "and" else or_(*clauses)


def build_audience_query(raw_filters: dict[str, Any], *, require_push: bool = False, require_active: bool = False) -> Select:
    definition = SegmentDefinition.model_validate(normalize_segment_filters(raw_filters))
    aggregate = _orders_aggregate()
    reviews = _review_aggregate()
    signals = _product_signal_aggregate()
    basket = _basket_activity_aggregate()
    statement = select(
        User,
        func.coalesce(aggregate.c.orders_count, 0).label("orders_count"),
        func.coalesce(aggregate.c.paid_total, 0).label("paid_total"),
        aggregate.c.last_order_at,
    ).outerjoin(aggregate, aggregate.c.user_id == User.id).outerjoin(
        reviews, reviews.c.user_id == User.id
    ).outerjoin(
        signals, signals.c.user_id == User.id
    ).outerjoin(
        basket, basket.c.user_id == User.id
    ).outerjoin(
        CustomerMarketingProfile, CustomerMarketingProfile.user_id == User.id
    )
    clauses = []
    group_clause = _group_clause(definition, aggregate=aggregate, review_aggregate=reviews, product_signal_aggregate=signals, basket_aggregate=basket)
    if group_clause is not None:
        clauses.append(group_clause)
    if require_active:
        clauses.append(User.is_active.is_(True))
    if require_push:
        clauses.append(exists(select(UserPushToken.id).where(UserPushToken.user_id == User.id)))
    if definition.exclusions:
        excluded_ids = select(AdminCustomerSegmentSnapshotItem.user_id).where(AdminCustomerSegmentSnapshotItem.segment_id.in_(definition.exclusions))
        clauses.append(~User.id.in_(excluded_ids))
    return statement.where(*clauses)


def build_static_segment_query(segment_id: int) -> Select:
    return select(
        User,
        func.count(Order.id).label("orders_count"),
        func.coalesce(func.sum(Order.grand_total).filter(Order.is_paid.is_(True), Order.is_canceled.is_(False)), 0).label("paid_total"),
        func.max(Order.created_at).label("last_order_at"),
    ).join(
        AdminCustomerSegmentSnapshotItem,
        AdminCustomerSegmentSnapshotItem.user_id == User.id,
    ).outerjoin(Order, Order.user_id == User.id).where(
        AdminCustomerSegmentSnapshotItem.segment_id == segment_id,
    ).group_by(User.id)


async def count_audience(db: AsyncSession, raw_filters: dict[str, Any], *, require_push: bool = False, require_active: bool = False) -> int:
    statement = build_audience_query(raw_filters, require_push=require_push, require_active=require_active).with_only_columns(User.id).order_by(None)
    return int((await db.execute(select(func.count()).select_from(statement.subquery()))).scalar_one())


async def count_static_segment(db: AsyncSession, segment_id: int, *, require_push: bool = False, require_active: bool = False) -> int:
    clauses = [AdminCustomerSegmentSnapshotItem.segment_id == segment_id]
    if require_active:
        clauses.append(User.is_active.is_(True))
    if require_push:
        clauses.append(exists(select(UserPushToken.id).where(UserPushToken.user_id == User.id)))
    statement = select(AdminCustomerSegmentSnapshotItem.user_id).join(User, User.id == AdminCustomerSegmentSnapshotItem.user_id).where(*clauses)
    return int((await db.execute(select(func.count()).select_from(statement.subquery()))).scalar_one())


async def list_audience_ids(
    db: AsyncSession,
    raw_filters: dict[str, Any],
    *,
    require_push: bool = False,
    require_active: bool = False,
    limit: int = MAX_CAMPAIGN_AUDIENCE + 1,
) -> list[int]:
    statement = build_audience_query(raw_filters, require_push=require_push, require_active=require_active).with_only_columns(User.id).order_by(User.id).limit(limit)
    return [int(value) for value in (await db.execute(statement)).scalars().all()]


async def list_static_segment_ids(
    db: AsyncSession,
    segment_id: int,
    *,
    require_push: bool = False,
    require_active: bool = False,
    limit: int = MAX_CAMPAIGN_AUDIENCE + 1,
) -> list[int]:
    clauses = [AdminCustomerSegmentSnapshotItem.segment_id == segment_id]
    if require_active:
        clauses.append(User.is_active.is_(True))
    if require_push:
        clauses.append(exists(select(UserPushToken.id).where(UserPushToken.user_id == User.id)))
    statement = select(AdminCustomerSegmentSnapshotItem.user_id).join(User, User.id == AdminCustomerSegmentSnapshotItem.user_id).where(*clauses).order_by(AdminCustomerSegmentSnapshotItem.user_id).limit(limit)
    return [int(value) for value in (await db.execute(statement)).scalars().all()]


async def count_segment_audience(db: AsyncSession, segment: AdminCustomerSegment, *, require_push: bool = False, require_active: bool = False) -> int:
    if segment.segment_type == "static":
        return await count_static_segment(db, segment.id, require_push=require_push, require_active=require_active)
    return await count_audience(db, segment.filters_json, require_push=require_push, require_active=require_active)


async def list_segment_audience_ids(
    db: AsyncSession,
    segment: AdminCustomerSegment,
    *,
    require_push: bool = False,
    require_active: bool = False,
    limit: int = MAX_CAMPAIGN_AUDIENCE + 1,
) -> list[int]:
    if segment.segment_type == "static":
        return await list_static_segment_ids(db, segment.id, require_push=require_push, require_active=require_active, limit=limit)
    return await list_audience_ids(db, segment.filters_json, require_push=require_push, require_active=require_active, limit=limit)


def validate_segment_filters(raw: dict[str, Any]) -> dict[str, Any]:
    try:
        return normalize_segment_filters(raw)
    except (ValidationError, ValueError) as error:
        raise ValueError(str(error)) from error
