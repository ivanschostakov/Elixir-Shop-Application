import re

from datetime import datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from starlette import status

from config import ufa_now
from src.normalize import (
    coerce_bool,
    coerce_decimal,
    coerce_int,
    extract_dict,
    extract_money,
    lower_optional_str,
    non_empty_str_list,
    normalize_email,
    optional_str,
    parse_iso_datetime,
)

REFERRAL_TIER_GROUP_MIN_ID = 26
REFERRAL_TIER_GROUP_MAX_ID = 43
PERCENT_DISCOUNT_TYPES = {"percent", "percentage"}
FIXED_AMOUNT_DISCOUNT_TYPES = {"fixed", "fixed_amount", "amount"}
BITRIX_SERIALIZED_PERCENT_TYPES = {"p"}
BITRIX_SERIALIZED_FIXED_TYPES = {"f", "s"}
BITRIX_SERIALIZED_VALUE_RE = re.compile(r'VALUE";[dis]:([^;]+)')
BITRIX_SERIALIZED_VALUE_TYPE_RE = re.compile(r'VALUE_TYPE";s:\d+:"([^"]+)"')


def extract_website_profile(payload: dict[str, Any]) -> dict[str, Any]:
    profile = payload.get("user")
    if not isinstance(profile, dict):
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Website returned invalid user payload")
    website_user_id = profile.get("id")
    if not isinstance(website_user_id, int) or website_user_id <= 0:
        raise HTTPException(status_code=status.HTTP_502_BAD_GATEWAY, detail="Website returned invalid website user id")

    return profile


def _normalize_discount_type(*candidates: Any) -> str | None:
    for raw_candidate in candidates:
        normalized = lower_optional_str(raw_candidate)
        if normalized in PERCENT_DISCOUNT_TYPES:
            return "percent"
        if normalized in FIXED_AMOUNT_DISCOUNT_TYPES:
            return "fixed_amount"
        if normalized in BITRIX_SERIALIZED_PERCENT_TYPES:
            return "percent"
        if normalized in BITRIX_SERIALIZED_FIXED_TYPES:
            return "fixed_amount"
    return None


def _extract_referral_tier(discounts: dict[str, Any]) -> tuple[int | None, str | None]:
    referral_tier = extract_dict(discounts.get("referral_tier"))
    tier_group_id = coerce_int(referral_tier.get("group_id")) or coerce_int(referral_tier.get("id"))
    tier_group_name = optional_str(referral_tier.get("group_name")) or optional_str(referral_tier.get("name"))
    if tier_group_id is not None and tier_group_name is not None:
        return tier_group_id, tier_group_name

    discount_groups = discounts.get("discount_groups") if isinstance(discounts.get("discount_groups"), list) else []
    legacy_group_id: int | None = None
    legacy_group_name: str | None = None
    for item in discount_groups:
        if not isinstance(item, dict):
            continue
        item_id = coerce_int(item.get("id"))
        item_name = optional_str(item.get("name"))
        if item_id is None or not (REFERRAL_TIER_GROUP_MIN_ID <= item_id <= REFERRAL_TIER_GROUP_MAX_ID):
            continue
        if legacy_group_id is None or item_id > legacy_group_id:
            legacy_group_id = item_id
            legacy_group_name = item_name

    return legacy_group_id, legacy_group_name


def _resolve_discount_amounts(item: dict[str, Any]) -> tuple[Decimal | None, Decimal | None]:
    discount_percent = coerce_decimal(item.get("discount_percent"))
    discount_amount = coerce_decimal(item.get("discount_amount"))
    if discount_percent is not None or discount_amount is not None:
        return discount_percent, discount_amount

    discount_type = _normalize_discount_type(
        item.get("discount_type"),
        item.get("discount_kind"),
        item.get("discount_mode"),
        item.get("calculation_mode"),
        item.get("type"),
    )
    discount_value = coerce_decimal(item.get("discount_value")) or coerce_decimal(item.get("value"))
    if discount_type == "percent":
        return discount_value, None
    if discount_type == "fixed_amount":
        return None, discount_value
    return None, None


def _parse_legacy_coupon_discount(item: dict[str, Any], discount: dict[str, Any]) -> tuple[str | None, Decimal | None]:
    serialized_discount = optional_str(discount.get("short_description")) or optional_str(item.get("description"))
    if not serialized_discount or "VALUE_TYPE" not in serialized_discount:
        return None, None

    value_type_match = BITRIX_SERIALIZED_VALUE_TYPE_RE.search(serialized_discount)
    value_match = BITRIX_SERIALIZED_VALUE_RE.search(serialized_discount)
    discount_type = _normalize_discount_type(value_type_match.group(1) if value_type_match else None)
    discount_value = coerce_decimal(value_match.group(1) if value_match else None)
    return discount_type, discount_value


def _resolve_coupon_discount(item: dict[str, Any], discount: dict[str, Any]) -> tuple[str | None, Decimal | None, str | None]:
    explicit_discount_type = _normalize_discount_type(
        item.get("discount_type"),
        item.get("discount_kind"),
        item.get("discount_mode"),
        item.get("calculation_mode"),
        discount.get("discount_type"),
        discount.get("discount_kind"),
        discount.get("discount_mode"),
        discount.get("calculation_mode"),
    )
    explicit_discount_value = (
        coerce_decimal(item.get("discount_value"))
        or coerce_decimal(discount.get("discount_value"))
        or coerce_decimal(discount.get("value"))
        or coerce_decimal(item.get("value"))
    )
    discount_currency = (
        optional_str(item.get("discount_currency"))
        or optional_str(discount.get("discount_currency"))
        or optional_str(item.get("currency"))
        or optional_str(discount.get("currency"))
    )
    if explicit_discount_type and explicit_discount_value is not None:
        return explicit_discount_type, explicit_discount_value, discount_currency

    legacy_discount_type = _normalize_discount_type(item.get("type"), discount.get("type"))
    legacy_discount_value = coerce_decimal(discount.get("value")) or coerce_decimal(item.get("value"))
    if legacy_discount_type and legacy_discount_value not in {None, Decimal("0")}:
        return legacy_discount_type, legacy_discount_value, discount_currency

    parsed_discount_type, parsed_discount_value = _parse_legacy_coupon_discount(item, discount)
    if parsed_discount_type and parsed_discount_value is not None:
        return parsed_discount_type, parsed_discount_value, discount_currency

    return explicit_discount_type or legacy_discount_type, explicit_discount_value or legacy_discount_value, discount_currency


def build_website_identity_payload(*, user_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    profile = extract_website_profile(payload)
    discounts = extract_dict(payload.get("discounts"))

    group_ids = [int(item) for item in profile.get("group_ids", []) if isinstance(item, int)]
    group_names = non_empty_str_list(profile.get("group_names"))
    custom_fields_raw = profile.get("custom_fields")
    custom_fields = {}
    if isinstance(custom_fields_raw, dict):
        custom_fields = {
            normalized_key: str(value)
            for key, value in custom_fields_raw.items()
            if (normalized_key := optional_str(key)) is not None and value is not None
        }

    active_coupons = discounts.get("active_coupons")
    recent_used_coupons = discounts.get("recent_used_coupons")
    discount_groups = discounts.get("discount_groups")

    return {
        "user_id": user_id,
        "website_user_id": int(profile["id"]),
        "website_login": optional_str(profile.get("login")) or f"website_{profile['id']}",
        "website_email": normalize_email(profile.get("email")),
        "website_name": optional_str(profile.get("name")),
        "website_last_name": optional_str(profile.get("last_name")),
        "website_second_name": optional_str(profile.get("second_name")),
        "website_phone": optional_str(profile.get("personal_phone")),
        "website_mobile": optional_str(profile.get("personal_mobile")),
        "website_city": optional_str(profile.get("personal_city")),
        "website_registered_at": parse_iso_datetime(profile.get("date_register")),
        "website_last_login_at": parse_iso_datetime(profile.get("last_login")),
        "group_ids": group_ids,
        "group_names": group_names,
        "custom_fields": custom_fields,
        "referral_program": discounts.get("referral_program") if isinstance(discounts.get("referral_program"), dict) else None,
        "bonus_account": discounts.get("bonus_account") if isinstance(discounts.get("bonus_account"), dict) else None,
        "discount_groups": discount_groups if isinstance(discount_groups, list) else [],
        "active_coupons": active_coupons if isinstance(active_coupons, list) else [],
        "recent_used_coupons": recent_used_coupons if isinstance(recent_used_coupons, list) else [],
        "raw_payload": payload,
        "last_synced_at": ufa_now(),
    }


def build_referral_profile_payload(*, website_identity_id: int, payload: dict[str, Any], last_synced_at: datetime) -> dict[str, Any] | None:
    profile = extract_website_profile(payload)
    discounts = extract_dict(payload.get("discounts"))
    custom_fields = extract_dict(profile.get("custom_fields"))
    referral_program = extract_dict(discounts.get("referral_program"))

    turnover_amount, turnover_currency = extract_money(
        referral_program.get("order_sum") if referral_program else custom_fields.get("UF_ORDER_SUMM")
    )
    monthly_amount, monthly_currency = extract_money(
        referral_program.get("sum_paid_orders_month") if referral_program else custom_fields.get("UF_SUM_PAID_ORDERS_MONTH")
    )

    tier_group_id, tier_group_name = _extract_referral_tier(discounts)
    referral_percent = coerce_decimal(referral_program.get("percent")) or coerce_decimal(custom_fields.get("UF_PERCENT"))

    data = {
        "website_identity_id": website_identity_id,
        "own_promo_code": optional_str(custom_fields.get("UF_PROMO")) or optional_str(referral_program.get("promo_code")),
        "referrer_website_user_id": coerce_int(custom_fields.get("UF_PARENT_ID")) or coerce_int(referral_program.get("parent_user_id")),
        "referrer_promo_code": optional_str(custom_fields.get("UF_PARENT_PROMO")),
        "referral_percent": referral_percent,
        "referral_turnover_amount": turnover_amount,
        "referral_turnover_currency": turnover_currency,
        "monthly_paid_orders_amount": monthly_amount,
        "monthly_paid_orders_currency": monthly_currency,
        "tier_group_id": tier_group_id,
        "tier_group_name": tier_group_name,
        "last_synced_at": last_synced_at,
    }
    has_meaningful_data = any(value is not None for key, value in data.items() if key not in {"website_identity_id", "last_synced_at"})
    return data if has_meaningful_data else None


def build_bonus_account_payload(*, website_identity_id: int, payload: dict[str, Any], last_synced_at: datetime) -> dict[str, Any] | None:
    bonus_account = extract_dict(payload.get("discounts")).get("bonus_account")
    if not isinstance(bonus_account, dict):
        return None

    balance, currency = extract_money(bonus_account.get("balance"))
    currency = currency or optional_str(bonus_account.get("currency")) or "RUB"
    is_active = coerce_bool(bonus_account.get("active"))
    data = {
        "website_identity_id": website_identity_id,
        "website_bonus_account_external_id": coerce_int(bonus_account.get("id")),
        "is_active": True if is_active is None else is_active,
        "balance": balance if balance is not None else Decimal("0.00"),
        "currency": currency,
        "website_created_at": parse_iso_datetime(bonus_account.get("date_create")),
        "last_synced_at": last_synced_at,
    }
    has_meaningful_data = any(
        value is not None for key, value in data.items() if key not in {"website_identity_id", "is_active", "balance", "last_synced_at"}
    )
    return data if has_meaningful_data or data["balance"] != Decimal("0.00") else data


def build_discount_entitlement_payloads(
    *, website_identity_id: int, payload: dict[str, Any], last_synced_at: datetime
) -> list[dict[str, Any]]:
    discounts = extract_dict(payload.get("discounts"))
    has_explicit_personal_discounts = isinstance(discounts.get("personal_discounts"), list)
    source_items = discounts.get("personal_discounts") if has_explicit_personal_discounts else discounts.get("discount_groups")
    if not isinstance(source_items, list):
        return []

    rows: list[dict[str, Any]] = []
    for item in source_items:
        if not isinstance(item, dict):
            continue
        source_name = optional_str(item.get("name")) or optional_str(item.get("title"))
        if not source_name:
            continue
        discount_percent, discount_amount = _resolve_discount_amounts(item)
        if discount_percent is None and discount_amount is None:
            continue

        source_id = optional_str(item.get("source_id")) or optional_str(item.get("website_source_id"))
        if source_id is None:
            source_id_int = coerce_int(item.get("id"))
            source_id = str(source_id_int) if source_id_int is not None else None
        is_stackable = coerce_bool(item.get("is_stackable"))
        is_active = coerce_bool(item.get("is_active"))
        rows.append(
            {
                "website_identity_id": website_identity_id,
                "source_kind": optional_str(item.get("source_kind")) or ("personal_discount" if has_explicit_personal_discounts else "group"),
                "website_source_id": source_id,
                "source_name": source_name,
                "discount_percent": discount_percent,
                "discount_amount": discount_amount,
                "currency": optional_str(item.get("currency")),
                "priority": coerce_int(item.get("priority")),
                "is_stackable": bool(is_stackable) if is_stackable is not None else False,
                "is_active": bool(is_active) if is_active is not None else True,
                "starts_at": parse_iso_datetime(item.get("starts_at")),
                "ends_at": parse_iso_datetime(item.get("ends_at")),
                "last_synced_at": last_synced_at,
            }
        )
    return rows


def build_coupon_payloads(*, website_identity_id: int, payload: dict[str, Any], last_synced_at: datetime) -> list[dict[str, Any]]:
    discounts = extract_dict(payload.get("discounts"))
    rows: list[dict[str, Any]] = []
    dedupe_keys: set[tuple[str | None, str | None, bool]] = set()

    def append_coupon(item: dict[str, Any], *, is_active_default: bool) -> None:
        coupon_code = optional_str(item.get("coupon"))
        if not coupon_code:
            return
        discount = item.get("discount") if isinstance(item.get("discount"), dict) else {}
        external_id = coerce_int(item.get("id"))
        active_flag = coerce_bool(item.get("active"))
        is_active = is_active_default if active_flag is None else active_flag
        key = (str(external_id) if external_id is not None else None, lower_optional_str(coupon_code), is_active)
        if key in dedupe_keys:
            return
        dedupe_keys.add(key)

        discount_type, discount_value, discount_currency = _resolve_coupon_discount(item, discount)
        description = optional_str(item.get("description")) or optional_str(discount.get("short_description"))
        rows.append(
            {
                "website_identity_id": website_identity_id,
                "website_coupon_external_id": external_id,
                "coupon_code": coupon_code,
                "discount_rule_id": coerce_int(item.get("discount_id")) or coerce_int(discount.get("id")),
                "discount_rule_name": optional_str(item.get("discount_name")) or optional_str(discount.get("name")),
                "discount_type": discount_type,
                "discount_value": discount_value,
                "discount_currency": discount_currency,
                "max_use": coerce_int(item.get("max_use")),
                "use_count": coerce_int(item.get("use_count")) or 0,
                "is_active": is_active,
                "description": description,
                "website_created_at": parse_iso_datetime(item.get("date_create")),
                "website_applied_at": parse_iso_datetime(item.get("date_apply")),
                "last_synced_at": last_synced_at,
            }
        )

    active_coupons = discounts.get("active_coupons")
    if isinstance(active_coupons, list):
        for item in active_coupons:
            if isinstance(item, dict):
                append_coupon(item, is_active_default=True)

    recent_used_coupons = discounts.get("recent_used_coupons")
    if isinstance(recent_used_coupons, list):
        for item in recent_used_coupons:
            if isinstance(item, dict):
                append_coupon(item, is_active_default=False)

    return rows
