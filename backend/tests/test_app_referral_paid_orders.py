from datetime import datetime, timezone
from types import SimpleNamespace

from src.app.services.referrals.paid_orders import _paid_order_promo, _period_bounds


def test_paid_order_promo_uses_only_applied_checkout_promo() -> None:
    order = SimpleNamespace(
        checkout_snapshot={
            "benefits": {
                "promo_code": "ENTERED-BUT-NOT-APPLIED",
                "applications": [
                    {
                        "kind": "promo",
                        "code": "APPLIED-REFERRER",
                    }
                ],
            }
        }
    )

    assert _paid_order_promo(order) == "APPLIED-REFERRER"


def test_paid_order_promo_ignores_unapplied_entered_code() -> None:
    order = SimpleNamespace(
        checkout_snapshot={
            "benefits": {
                "promo_code": "INVALID-OR-OWN-CODE",
                "applications": [],
            }
        }
    )

    assert _paid_order_promo(order) is None


def test_period_bounds_handle_year_boundary() -> None:
    paid_at = datetime(2026, 12, 31, 22, 10, tzinfo=timezone.utc)

    assert _period_bounds(paid_at) == (
        datetime(2026, 12, 1).date(),
        datetime(2027, 1, 1).date(),
    )
