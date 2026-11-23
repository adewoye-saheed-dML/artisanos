# ArtisanOS Deployment Guide (Render Backend + Render Frontend + GitHub Actions)

This guide walks step-by-step through deploying both the **Django Backend (`apps/backend`)** and **Next.js Frontend (`apps/frontend`)** on **Render**, wired to the GitHub Actions CI/CD pipeline (`main` → `stage` → `prod`).

---

## 1. Branching & CI/CD Flow

| Branch | Workflow | What Happens |
| --- | --- | --- |
| `main` | `.github/workflows/ci.yml` | Runs full Backend (Django checks, migrations, OpenAPI schema, `collectstatic`, PostgreSQL `pytest`) + Frontend (`lint`, `typecheck`, `build`). No deploy. |
| `stage` | `.github/workflows/deploy-stage.yml` | Runs CI → triggers Render Staging Backend deploy hook → verifies `/api/v1/health/` → triggers Render Staging Frontend deploy hook → smoke-checks frontend URL. |
| `prod` | `.github/workflows/deploy-prod.yml` | Same flow targeting the **`production`** GitHub Environment (supports Required Reviewers) and Render Production services. |

Create and push `stage` and `prod` branches first:

```bash
git checkout main
git pull origin main
git checkout -b stage && git push -u origin stage
git checkout -b prod && git push -u origin prod
git checkout main
```

---

## 2. Step-by-Step Render Setup

You can deploy via **Render Blueprint** (`render.yaml`) **OR** create each service manually in the Render Dashboard.

### Option A: One-Click Blueprint (`render.yaml`)
1. Go to **Render Dashboard → New → Blueprint**.
2. Connect your GitHub repo (`artisanos`).
3. Render reads [`render.yaml`](../render.yaml) and creates:
   - `artisanos-db-stage` & `artisanos-db-prod` (PostgreSQL 16)
   - `artisanos-api-stage` & `artisanos-api-prod` (Django Backend)
   - `artisanos-web-stage` & `artisanos-web-prod` (Next.js Frontend)
4. Fill in the prompted `sync: false` environment variables listed in **Section 3** below.

### Option B: Manual Setup in Render Dashboard

Repeat these 3 steps for **Staging** (branch `stage`) and **Production** (branch `prod`):

#### Step 1 — Create PostgreSQL Database
1. **New → PostgreSQL**
2. Name: `artisanos-db-stage` (or `artisanos-db-prod`)
3. Pick the same **Region** you will use for the Backend and Frontend services.
4. Copy the **Internal Database URL** once created.

#### Step 2 — Create Backend Web Service (Django)
1. **New → Web Service** → connect your GitHub repo.
2. Configure:
   - **Name**: `artisanos-api-stage` (or `artisanos-api-prod`)
   - **Branch**: `stage` (or `prod`)
   - **Root Directory**: `apps/backend`
   - **Runtime**: `Python 3`
   - **Build Command**:
     ```bash
     pip install -r requirements.txt && python manage.py collectstatic --noinput
     ```
   - **Start Command**:
     - On **Free plan**:
       ```bash
       python manage.py migrate --noinput && python manage.py seed_templates && python manage.py seed_plans && gunicorn artisanos.wsgi:application --bind 0.0.0.0:$PORT --workers 2 --timeout 120
       ```
     - On **Paid plan (Starter+)**: put `python manage.py migrate --noinput && python manage.py seed_templates && python manage.py seed_plans` in **Pre-Deploy Command** and set **Start Command** to:
       ```bash
       gunicorn artisanos.wsgi:application --bind 0.0.0.0:$PORT --workers 3 --timeout 120
       ```
   - **Health Check Path**: `/api/v1/health/`
   - **Auto-Deploy**: **Off** (so GitHub Actions only deploys after CI passes)
3. Add all **Backend Environment Variables** from Section 3.
4. Deploy and verify `https://<your-backend>.onrender.com/api/v1/health/` returns `{"status":"ok","database":"connected",...}`.
5. Go to **Settings → Deploy Hook** and copy the Deploy Hook URL.

#### Step 3 — Create Frontend Web Service (Next.js)
1. **New → Web Service** → connect your GitHub repo.
2. Configure:
   - **Name**: `artisanos-web-stage` (or `artisanos-web-prod`)
   - **Branch**: `stage` (or `prod`)
   - **Root Directory**: `apps/frontend`
   - **Runtime**: `Node`
   - **Build Command**:
     ```bash
     npm ci && npm run build
     ```
   - **Start Command**:
     ```bash
     npx next start -H 0.0.0.0 -p $PORT
     ```
   - **Auto-Deploy**: **Off**
3. Add all **Frontend Environment Variables** from Section 3 (pointing `BACKEND_INTERNAL_URL` to your Backend URL from Step 2).
4. Once deployed, copy the Frontend URL (e.g. `https://artisanos-web-stage.onrender.com`) and update `CORS_ALLOWED_ORIGINS` and `CSRF_TRUSTED_ORIGINS` on the Backend service.
5. Go to **Settings → Deploy Hook** and copy the Frontend Deploy Hook URL.

---

## 3. Environment Variables Reference

### Backend (`apps/backend`) on Render

| Variable | Required | Example Value (Staging) | Notes |
| --- | --- | --- | --- |
| `PYTHON_VERSION` | Yes | `3.12.8` | Matches CI Python 3.12 |
| `DJANGO_DEBUG` | Yes | `False` | Always `False` in stage/prod |
| `DJANGO_SECRET_KEY` | Yes | *(generate 50+ char random string)* | Different secret per environment |
| `DATABASE_URL` | Yes | `postgresql://...` | Render PostgreSQL **Internal Database URL** |
| `DJANGO_ALLOWED_HOSTS` | Yes | `artisanos-api-stage.onrender.com` | Comma-separated hostnames (no `https://`). Add custom domain too if used. |
| `CORS_ALLOWED_ORIGINS` | Yes | `https://artisanos-web-stage.onrender.com` | Exact frontend origin(s) with `https://`, no trailing slash |
| `CSRF_TRUSTED_ORIGINS` | Yes | `https://artisanos-web-stage.onrender.com,https://artisanos-api-stage.onrender.com` | Frontend + Backend origins with `https://`, no trailing slash |
| `AUTH_COOKIE_SECURE` | Recommended | `True` | Defaults to `True` when `DJANGO_DEBUG=False` |
| `AUTH_COOKIE_SAMESITE` | Recommended | `Lax` | Works cleanly because Next.js proxies `/api/v1/*` on the same origin |
| `CSRF_COOKIE_SECURE` | Recommended | `True` | Defaults to `True` when `DJANGO_DEBUG=False` |
| `SESSION_COOKIE_SECURE` | Recommended | `True` | Defaults to `True` when `DJANGO_DEBUG=False` |
| `FEATURE_CAMERA_MEASUREMENTS` | Optional | `False` | Keep `False` until Phase 4 |
| `PAYSTACK_SECRET_KEY` | Yes (payments) | `sk_test_...` (stage) / `sk_live_...` (prod) | Required for Paystack webhooks |

### Frontend (`apps/frontend`) on Render

| Variable | Required | Example Value (Staging) | Notes |
| --- | --- | --- | --- |
| `NODE_VERSION` | Yes | `22.12.0` | Matches CI Node 22 |
| `NEXT_PUBLIC_API_BASE_URL` | Yes | `/api/v1` | Keeps auth/CSRF cookies same-origin via Next.js proxy route |
| `BACKEND_INTERNAL_URL` | Yes | `https://artisanos-api-stage.onrender.com` | Backend URL (**no trailing slash**) |
| `NEXT_PUBLIC_SITE_URL` | Yes | `https://artisanos-web-stage.onrender.com` | Used for SEO metadata, `sitemap.xml`, and `robots.txt` (**no trailing slash**) |

---

## 4. Connect GitHub Actions Environments & Secrets

In GitHub go to **Settings → Environments** and create **`staging`** and **`production`** (recommended: enable **Required reviewers** on `production`).

Inside **each** environment (`staging` and `production`), add:

### Environment Secrets
| Secret | Value |
| --- | --- |
| `RENDER_BACKEND_DEPLOY_HOOK_URL` | Render Backend service → Settings → Deploy Hook URL |
| `RENDER_FRONTEND_DEPLOY_HOOK_URL` | Render Frontend service → Settings → Deploy Hook URL |

### Environment Variables
| Variable | Example Value |
| --- | --- |
| `BACKEND_HEALTHCHECK_URL` | `https://artisanos-api-stage.onrender.com/api/v1/health/` |
| `FRONTEND_SMOKE_URL` | `https://artisanos-web-stage.onrender.com` |

---

## 5. One-Time Post-Deploy Seed (Nigerian Locations)

Migrations, measurement templates (`seed_templates`), and billing plans (`seed_plans`) run automatically on deploy. After your first successful deploy, open the Render Backend **Shell** (or run locally against the External DB URL) once to load Nigerian states/LGAs/wards/polling units:

```bash
# Full INEC dataset (~176k polling units, 8,809 wards, 774 LGAs, 37 states):
python manage.py sync_inec_polling_units

# Or lightweight offline baseline:
python manage.py seed_nigeria_locations
```

Optional: create a Django superuser for `/admin/`:

```bash
python manage.py createsuperuser
```
