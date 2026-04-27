import sys
from datetime import datetime
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from src.app.services.website_identities.payloads import (
    build_bonus_account_payload,
    build_coupon_payloads,
    build_discount_entitlement_payloads,
    build_referral_profile_payload,
)


def _payload() -> dict:
    return {
        "user": {
            "id": 91001,
            "login": "payload-user",
            "custom_fields": {
                "UF_PROMO": "WELCOME",
                "UF_PARENT_ID": "7",
                "UF_PERCENT": "19",
                "UF_ORDER_SUMM": "3060.33|RUB",
            },
        },
        "discounts": {
            "referral_program": {
                "promo_code": "WELCOME",
                "parent_user_id": 7,
                "percent": None,
                "order_sum": {"raw": "3060.33|RUB", "amount": 3060.33, "currency": "RUB"},
            },
            "referral_tier": {"group_id": 33, "group_name": "Заказы больше 100 т. р."},
            "bonus_account": {"id": 91001, "balance": 125.5, "active": True},
            "discount_groups": [{"id": 33, "name": "Заказы больше 100 т. р."}],
            "personal_discounts": [
                {
                    "id": 7,
                    "source_kind": "group",
                    "name": "VIP",
                    "discount_type": "percent",
                    "discount_value": 5.0,
                    "currency": "RUB",
                    "is_active": True,
                }
            ],
            "active_coupons": [
                {
                    "id": 991,
                    "coupon": "LEGACY-3",
                    "type": 4,
                    "discount": {
                        "id": 24,
                        "name": "Legacy 3%",
                        "short_description": 'a:4:{s:4:"TYPE";s:8:"Discount";s:5:"VALUE";d:3;s:11:"LIMIT_VALUE";i:0;s:10:"VALUE_TYPE";s:1:"P";}',
                        "value": 0,
                        "currency": "RUB",
                    },
                }
            ],
        },
    }


def test_build_referral_profile_payload_prefers_referral_tier_and_custom_percent():
    data = build_referral_profile_payload(website_identity_id=1, payload=_payload(), last_synced_at=datetime.utcnow())

    assert data is not None
    assert data["tier_group_id"] == 33
    assert data["tier_group_name"] == "Заказы больше 100 т. р."
    assert float(data["referral_percent"]) == 19.0


def test_build_bonus_account_payload_defaults_currency_to_rub():
    data = build_bonus_account_payload(website_identity_id=1, payload=_payload(), last_synced_at=datetime.utcnow())

    assert data is not None
    assert str(data["balance"]) == "125.5"
    assert data["currency"] == "RUB"


def test_build_discount_entitlement_payloads_use_personal_discounts_only_for_actionable_rows():
    rows = build_discount_entitlement_payloads(website_identity_id=1, payload=_payload(), last_synced_at=datetime.utcnow())

    assert len(rows) == 1
    assert rows[0]["source_name"] == "VIP"
    assert float(rows[0]["discount_percent"]) == 5.0


def test_build_discount_entitlement_payloads_skip_legacy_tiers_without_numeric_values():
    payload = _payload()
    payload["discounts"]["personal_discounts"] = []

    rows = build_discount_entitlement_payloads(website_identity_id=1, payload=payload, last_synced_at=datetime.utcnow())

    assert rows == []


def test_build_coupon_payloads_parse_legacy_serialized_discount():
    rows = build_coupon_payloads(website_identity_id=1, payload=_payload(), last_synced_at=datetime.utcnow())

    assert len(rows) == 1
    assert rows[0]["coupon_code"] == "LEGACY-3"
    assert rows[0]["discount_type"] == "percent"
    assert float(rows[0]["discount_value"]) == 3.0
