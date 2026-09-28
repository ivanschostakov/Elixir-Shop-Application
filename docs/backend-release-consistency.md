# Backend release consistency

The API and all seven Python workers share one Docker image. Build it once with
`docker compose build backend-api`; the other backend services reference the same
`elixir-shop-backend:production` image by default. The admin SPA and Redis are
separate images.

For an immutable release, set `SHOP_BACKEND_IMAGE` to the same versioned image
for build and deployment. Keep the previous image available for rollback.
Use the existing production override files as well as `docker-compose.yml`:
they can preserve service-specific environment settings. Do not commit resolved
Compose configuration or overrides containing credentials.

Recreate the API and workers from the same release, verify API readiness at
`/api/v1/health/ready`, and verify each worker stays running without restarts.
Persistent media, logs, database data and secrets must remain outside the image.
