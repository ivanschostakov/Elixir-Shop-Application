# MoySklad transition: preparation, not financial cutover

## Implemented

- Authenticated read-only settlement endpoint and opt-in account view. See
  `frontend/docs/moysklad-account-view.md` for cache and rollout behavior.
- Exact, unambiguous phone/email lookup; no first fuzzy match. Saved customer
  links are retained during phone login. Conflicting contact information is not
  grounds for automatic relinking.
- Order synchronization no longer overwrites contacts, name or externalCode of
  an existing shared counterparty. A missing saved link requires manual review.
- New orders freeze `client_platform` in their checkout snapshot. iOS, Android
  and Telegram/web have separate configurable sales channels; old/unknown
  platforms retain the previous common channel. Existing MS documents are not
  rewritten when the application retries synchronization.
- Read-only reconciliation exporter:
  `python -m src.app.services.benefits.settlement_audit` from `backend` with the
  application's environment. It uses a read-only SQL transaction and GET only.
  The JSON contains sensitive financial records and identifiers, but no names,
  emails, phone numbers or tokens. Store it outside Git with restrictive access,
  and obtain authorization for its destination before exporting production data.

## Channel configuration

After verifying these entities still exist in the target MS account, set:

```env
MOY_SKLAD_IOS_SALES_CHANNEL_HREF=https://api.moysklad.ru/api/remap/1.2/entity/saleschannel/52d06030-bbe7-11f1-0a80-016f000f8af5
MOY_SKLAD_ANDROID_SALES_CHANNEL_HREF=https://api.moysklad.ru/api/remap/1.2/entity/saleschannel/58234296-bbe7-11f1-0a80-14c400102f30
MOY_SKLAD_TELEGRAM_SALES_CHANNEL_HREF=https://api.moysklad.ru/api/remap/1.2/entity/saleschannel/46af5b06-bbe7-11f1-0a80-04e500103d97
```

Keep the existing `MOY_SKLAD_SALES_CHANNEL_HREF` as fallback. These headers are
analytics metadata, not an authorization boundary. Web means Telegram because
the current web app is gated to Telegram. A future standalone web storefront
must have a distinct platform mapping.

## Verified production counts on 2026-09-29

Read-only aggregate diagnostics found 26 users, 19 distinct saved MS links and
7 unlinked users. All 19 linked cards could be read: 5 accumulation programs,
14 referral programs. Two users have a different email on their MS card.
This is a review flag, not proof that either value or the link is incorrect.
Local records contain 12 applied credits totaling 11,583 points and 0 locally
allocated spent points, plus 8 orders (3 paid, 5 pending). Points are not a
confirmed ruble migration amount; do not add them to the new balance.

## Required before financial cutover

1. Approve client identities and a reconciliation of the old ledger against MS
   bonus transactions AND cash payment documents. Do not import all credits
   again. Keep immutable operation IDs for any approved transfer.
2. Confirm the owner/API for program and promo changes, including effective
   dates. The opt-in view does not provide program editing.
3. Obtain the atomic reservation/settlement contract used by every storefront.
   A GET of the signed balance, or a local PostgreSQL lock, cannot prevent the
   website and application spending the same funds concurrently.
4. Confirm invoice ownership, zero/partial payment, delivery coverage,
   cancellations and refunds with MS automation. Currently the application
   creates its own invoiceout and charges its existing order total.
5. Define the per-order cutover boundary and treatment of legacy pending
   orders, retries and reversals. Only then disable legacy cashback/referral,
   EARNING/SPENDING and expiry writers, preserving historical operations.

No Hub endpoints, financial write contract or migration amounts are invented
by this change. Neither the opt-in display nor channel separation switches off
the current accounting engine. Do not enable the new UI for customers as though
its displayed cash balance were already spendable in the existing checkout.

## Deployment

Use the single shared versioned backend image and production overrides described
in `docs/backend-release-consistency.md`. No database schema migration is needed
for this preparation. Deploy API and all Python workers consistently, verify
`/api/v1/health/ready`, and retain the previous image for rollback. Financial
settings and `EXPO_PUBLIC_MS_ACCOUNT_VIEW_ENABLED` must stay unchanged/off until
the cutover acceptance above is complete.
