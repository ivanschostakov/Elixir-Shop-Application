# Read-only MoySklad account view

The opt-in account view reads `GET /api/v1/users/me/referral-profile/settlement`.
Deploy the backend endpoint before enabling the view. Set
`EXPO_PUBLIC_MS_ACCOUNT_VIEW_ENABLED=true` in the frontend build environment and
rebuild the application. The default is false; the existing discounts screen and
promo-code management remain unchanged when disabled. This is a build-time flag,
not a remotely controlled runtime switch.

## Data contract

- Only the authenticated user's `moysklad_counterparty_id` is used. No search,
  automatic relinking, or counterparty creation happens from this endpoint.
- The counterparty report's signed `balance` is displayed in rubles; it is not
  the bonus-points wallet and must not authorize spending.
- The counterparty's `salesAmount` is converted from minor units into rubles.
- Program values are explicit: 0 none, 1 accumulation, 2 referral. Missing or
  unrecognized values stay unknown. A promo code never implies a program.
- All upstream operations are GET requests. No local financial rows or MoySklad
  entities are modified. Existing checkout and accrual logic is unchanged.

## Availability

Redis keeps a last-successful snapshot for seven days, fresh for five minutes.
Failed refreshes show the old value with its timestamp and a stale warning,
never a fabricated zero. No saved value means unavailable. No counterparty link
means unlinked. Per-customer locks, a shared refresh gate, error backoff and a
global HTTP 429 cooldown prevent request bursts. Redis failure stops new reads
from MoySklad rather than removing these controls.

The API returns `Cache-Control: private, no-store`. The screen drops in-memory
data on account changes. Promo codes are read-only in the opt-in view; keep the
legacy screen enabled until the corresponding financial workflow is ready.

## Verification and rollout boundary

Run backend `tests/test_settlement.py` and the frontend regression tests and
typecheck. Exercise positive, negative and zero balances, unknown program,
unlinked accounts, stale data and account switching before enabling production.
This change does not migrate existing balances, disable financial writers,
connect Hub, change order sales channels or reconcile customer identities.
