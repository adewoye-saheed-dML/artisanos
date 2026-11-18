# ArtisanOS

Multi-tenant SaaS platform for measurement-based artisan businesses (starting with tailoring, with configurable measurement templates for shoemaking, leatherwork, and other custom crafts).

## Monorepo Structure

- `apps/backend/` — Django + Django REST Framework + PostgreSQL API (`/api/v1/`)
- `apps/frontend/` — Next.js (App Router) + TypeScript + Tailwind CSS + TanStack Query web application
- `docs/` — Architecture ([architecture.md](docs/architecture.md)), API contract ([api-contract.md](docs/api-contract.md)), and decisions ([DECISIONS.md](docs/DECISIONS.md))
- `docker-compose.yml` — PostgreSQL 16 local database container

## Implemented Scope (Phase 0 & Phase 1 MVP)

1. **Authentication**: Email/password registration, login, logout, token refresh, and CSRF-protected `HttpOnly` JWT cookies (no tokens stored in `localStorage`).
2. **Multi-tenant Organizations**: Workspace creation during onboarding, workspace switcher, membership roles (`owner`, `manager`, `artisan`, `sales_assistant`), and server-side tenant isolation on every endpoint via verified `X-Organization-Id`.
3. **Customer Management**: Organization-scoped customer CRUD, search, and soft archiving.
4. **Configurable Measurement Templates**: Versioned `MeasurementTemplate` → `MeasurementTemplateVersion` → `MeasurementField` schema seeded with a 16-field **Standard Tailoring** template and a **Standard Shoemaking** reference template, plus custom organization template creation.
5. **Manual Measurement Recording & History**: `cm` / `in` unit-aware validation, immutable revision history (editing creates a new profile version and marks the prior version `superseded`), plus expiring public customer measurement request links (`/m/[token]`).
6. **Tailoring Orders & Real Dashboard**: Sequential order numbering, validated status transition state machine, immutable `OrderStatusEvent` timeline, frozen `measurement_snapshot` on confirmation, and real database-backed dashboard metrics.

> **Note:** AI/camera measurement estimation is **not** implemented in Phase 0/1; it is disabled behind `FEATURE_CAMERA_MEASUREMENTS=False`.

## Local Setup

### 1. Environment Configuration
```bash
cp .env.example .env
```

### 2. PostgreSQL Database
Using Docker Compose:
```bash
docker compose up -d postgres
```
Or using a local PostgreSQL 16 service:
Ensure a PostgreSQL user `artisanos` and database `artisanos` exist matching `.env` (or update `DATABASE_URL`).

### 3. Backend Setup & Run
```bash
cd apps/backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py seed_templates
python manage.py seed_plans
# Optional: seed realistic, clearly labeled demo workspace & sample records
python manage.py seed_demo_data
python manage.py runserver 0.0.0.0:8000
```

API docs are available at `http://127.0.0.1:8000/api/v1/docs/`.

### 4. Frontend Setup & Run
```bash
cd apps/frontend
npm install
npm run dev
```

Open `http://localhost:3000`. Next.js proxies `/api/v1/*` to `BACKEND_INTERNAL_URL` (`http://127.0.0.1:8000`).

## Running Tests & Checks

### Backend Tests (PostgreSQL)
```bash
cd apps/backend
source .venv/bin/activate
pytest
```

### Frontend Checks
```bash
cd apps/frontend
npm run lint
npm run typecheck
npm run build
```
