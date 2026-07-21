# Elixir Shop Admin

`admin-web` is a separate desktop-first React application for store operations. It is served through the same origin as the FastAPI admin API, so the HttpOnly refresh cookie never needs cross-origin access.

## Local development

1. Start PostgreSQL, Redis and the backend.
2. Apply the migration: `cd backend && alembic upgrade head`.
3. If the database has no administrator, grant access to an existing registered application user:

   `cd backend && python -m src.scripts.bootstrap_admin admin@example.com`

4. Start the SPA: `cd admin-web && npm install && npm run dev`.
5. Open `http://localhost:4173`. The first sign-in requires TOTP setup.

The Vite server proxies `/api` to `http://127.0.0.1:8000`. Override this with `ADMIN_API_PROXY_TARGET` in `admin-web/.env` when needed.

## Production

Run `docker compose up -d --build admin-web worker-admin-jobs`. The admin worker consumes idempotent long-running operations from Redis. The web container serves the SPA on `127.0.0.1:8080` and proxies `/api`, `/media` and `/health` to `backend-api`. Put the existing HTTPS reverse proxy in front of port 8080.

Production backend settings:

- `ADMIN_COOKIE_SECURE=true`
- `ADMIN_READ_ONLY=true` during the staging/read-only rollout
- `CORS_ALLOWED_ORIGINS` limited to production origins (the admin itself uses same-origin requests)

After validation, turn `ADMIN_READ_ONLY` off section by section operationally. Administrators can be disabled and their sessions revoked from Settings → Staff.

## Reviews

Review submission is public and rate-limited. Signed-in users keep their profile identity; guests are stored as guests. Every new review starts unpublished and appears in Content → Reviews. Only a user with `reviews.moderate` can publish or reject it. Public product endpoints and rating aggregates include only published, non-rejected reviews.
