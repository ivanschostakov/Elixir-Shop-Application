# Release Readiness Audit

Date: 2026-05-01

## Summary

This pass focused on release readiness for the active backend and frontend app code. It repaired the broken frontend quality gates, removed noisy backend test startup side effects, fixed CDEK country-code test drift, and corrected recommendation ordering/exclusion behavior.

## Fixed

- Frontend lint and typecheck now ignore archived/generated folders: `backups`, `web-backup`, and `scripts/react-native-yamap-patches`.
- Added `npm run typecheck` for the Expo/TypeScript app.
- Backend tests now disable app lifespan background workers without disabling notification processor behavior.
- CDEK delivery country coverage now derives from the backend supported-country list, with `EU` explicitly verified as unsupported.
- Recommendations now sort by affinity, shared category count, signal recency, product priority, then product recency/id.
- Recommendations now exclude products that directly generated user affinity, such as viewed or favorited source products.

## Verification

- `npm run lint`: passed.
- `npm run typecheck`: passed.
- `ONEC_SYNC_ENABLED=0 NOTIFICATIONS_ENABLED=0 ./.venv/bin/python -m pytest tests/test_delivery_cdek_router.py tests/test_recommendations_api.py -q`: passed, 18 tests.
- `./.venv/bin/python -m pytest`: passed, 168 tests with 7 deprecation warnings.

## Remaining Release Risks

- Backend CORS still allows all origins; restrict this before production if the API is public.
- Backend tests depend on a local Postgres database and are not fully hermetic.
- Native iOS and Android builds were not rebuilt or smoke-tested in this pass.
- The web app remains intentionally disabled in `frontend/app/_layout.tsx`.
- Existing Python deprecation warnings remain for FastAPI 422 naming and timezone-naive `datetime.utcnow()` usage in tests.
