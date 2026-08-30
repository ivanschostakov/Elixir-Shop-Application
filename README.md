# Elixir Peptide Commerce Platform

Production-oriented commerce platform spanning a React Native customer application, FastAPI backend, React administration interface, AI-assisted customer workflows, and business-system integrations.

[View the Android application on Google Play](https://play.google.com/store/apps/details?id=com.elixirpeptide.elixirpeptide)

## Product Surfaces

- **Mobile application:** catalog, search, favorites, cart, checkout, delivery, payments, customer profile, notifications, and community features.
- **Backend:** authentication, catalog, orders, loyalty, reviews, support, AI chat, integrations, automation, and administration APIs.
- **Admin web:** operational dashboards, marketing, communications, tasks, integrations, readiness, and analytics.
- **Business integrations:** Bitrix24, amoCRM, MoySklad, 1C, CDEK, Yandex delivery/maps, Telegram, email, push notifications, and payment services.

## Architecture

```text
React Native / Expo app        React admin web
            \                    /
             -> FastAPI backend
                  -> PostgreSQL and Redis
                  -> background workers
                  -> AI and messaging services
                  -> CRM, inventory, delivery, and payment integrations
```

## Technology

- Python, FastAPI, SQLAlchemy, Alembic, PostgreSQL, Redis
- React Native, Expo, React 19, TypeScript
- Docker and Docker Compose
- pytest, Vitest, ESLint, and TypeScript type checking

## Local Development

Copy the relevant environment templates before starting any service. Never place production credentials in committed files.

### Full stack with Docker

```bash
cp backend/.env.example backend/.env
docker compose up --build
```

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
alembic upgrade head
```

### Mobile application

```bash
cd frontend
npm ci
cp .env.example .env.local
npm run start
```

### Admin web

```bash
cd admin-web
npm ci
cp .env.example .env.local
npm run dev
```

## Verification

```bash
cd backend && pytest -q
cd ../admin-web && npm test && npm run typecheck
cd ../frontend && npm run lint && npm run typecheck
```

## Repository Hygiene

- Generated contracts, legal documents, packaged integrations, logs, and local media belong outside Git.
- Public demonstrations should use synthetic customer, order, and support data.
- Secrets must be supplied through local environment files or a deployment secret manager.
