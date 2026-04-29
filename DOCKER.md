# Docker

This repo has a multi-service Docker Compose setup for the local app ecosystem:

- Your Mac's local Postgres
- Redis
- FastAPI backend
- Expo Metro for the iOS dev client
- Cloudflared tunnel

Start the full stack:

```bash
docker compose up --build
```
The backend listens on `http://localhost:8000`, Metro on `http://localhost:8081`, your Mac Postgres stays on `localhost:5432`, and Redis is available on `localhost:6379`. Docker defaults expose the app to the iOS dev client through `10.131.51.173`.

Expo prints the iOS dev-client QR from the `frontend` service. If you started Compose in the background, follow that service:

```bash
docker compose logs -f frontend
```

For just the QR/Metro server without backend or tunnel:

```bash
docker compose up --build frontend
```

Cloudflared uses `frontend/cloudflared/elixirshop.docker.yml`:

- `https://api-elixirshop.devsivanschostakov.org` -> backend
- `https://elixirshop.devsivanschostakov.org` -> Expo Metro

Backend configuration and credentials are injected by Docker Compose from `backend/.env`. The backend application reads only process environment variables; it does not call `load_dotenv`. Keep the local backend values there, including `POSTGRES_HOST=localhost`.

Inside Docker Desktop on macOS, a container's literal `localhost` is the container itself, not your Mac. Compose keeps `backend/.env` local-friendly and only overrides the backend container runtime host to `host.docker.internal`, which is Docker Desktop's stable address for your Mac. Credentials still come from Docker-injected environment variables sourced from `backend/.env`.

Backend source is bind-mounted from `./backend`, so static files are served from the real project media folder at `backend/media`. Do not mount a named volume over `/app/backend/media`; it will hide the product images from the container.

Product image URLs are generated with `BACKEND_PUBLIC_API_BASE_URL` in Docker so the iOS dev client receives URLs reachable from the phone, for example `http://10.131.51.173:8000/media/...`, not container-local `localhost` URLs.

For local Docker-only overrides, create a root `.env` from `.env.docker.example`. Keep backend credentials out of the root Docker `.env`; it is only for Compose ports, cloudflared credential path, and frontend public env values. The frontend container sets `EXPO_NO_DOTENV=1`, so Expo also uses the environment injected by Compose instead of reading `frontend/.env`.

Docker runs the Metro server that the iOS dev client connects to. Building and installing the native iOS dev client still has to run on macOS/Xcode:

```bash
cd frontend
npm run ios
```

After the dev client is installed, keep the Docker stack running and open the dev client against Metro on `10.131.51.173:8081`. The frontend service runs the same dev-client start flow as local development, without passing an explicit `--host` flag. If your Mac's LAN IP changes, update `REACT_NATIVE_PACKAGER_HOSTNAME`, `FRONTEND_API_BASE_URL`, `EXPO_PUBLIC_API_BASE_URL`, and `BACKEND_PUBLIC_API_BASE_URL` in the root `.env` before starting Compose.

If reloads do not fire on Docker Desktop, set `CHOKIDAR_USEPOLLING=true` and `WATCHPACK_POLLING=true` in the root `.env`. Polling costs more memory, so keep it off unless you need it.
