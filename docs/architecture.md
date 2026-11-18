# ArtisanOS Architecture (Phase 0 & Phase 1 MVP)

## 1. System Overview

ArtisanOS is structured as a modular monorepo:
- `apps/backend/`: Django + Django REST Framework API backed by PostgreSQL.
- `apps/frontend/`: Next.js (App Router) + TypeScript web application.
- `docs/`: Architecture, API contract, and architectural decision records.

The Next.js frontend proxies `/api/v1/*` requests to the Django backend (`BACKEND_INTERNAL_URL`), allowing `HttpOnly` JWT cookies and CSRF cookies to operate cleanly on the same origin without storing authentication tokens in `localStorage`.

## 2. Multi-Tenant Isolation Model

- **Tenant root**: `Organization` (UUID primary key, slug, category, currency, preferred unit).
- **Membership**: `Membership` connects `User` and `Organization` with `role` (`owner`, `manager`, `artisan`, `sales_assistant`) and `status` (`active`, `invited`, `suspended`).
- **Server-side enforcement**:
  1. Every tenant-scoped endpoint requires `X-Organization-Id` (UUID).
  2. `core.tenancy.ActiveOrganizationPermission` verifies that `request.user` holds an `active` `Membership` for that organization and attaches `request.organization` and `request.membership`.
  3. Querysets always filter by `organization=request.organization`.
  4. Serializers and domain services validate that referenced records (`Customer`, `MeasurementProfile`, `MeasurementTemplate`) belong to `request.organization` (or are published system templates where applicable).

## 3. Configurable Measurement Engine

Measurements are data-driven rather than hard-coded for tailoring:
- `MeasurementTemplate` -> `MeasurementTemplateVersion` -> `MeasurementField`.
- Templates can be system-wide (`organization=None`) or organization-owned.
- `MeasurementProfile` records measurements for a `Customer` against a specific `MeasurementTemplateVersion`, `unit_system` (`cm` or `in`), `source`, and `status` (`draft`, `submitted`, `needs_review`, `verified`, `superseded`).
- **Immutability & History**: Updating a measurement profile's values or unit creates a new `MeasurementProfile` version (`version_number + 1`, linked via `parent_profile`) and marks the prior profile `superseded` (`is_latest=False`), preserving historical records for confirmed orders.
- **Measurement Requests**: Artisans can issue expiring, single-use `MeasurementRequest` links (`/m/{token}`) backed by SHA-256 token hashes. Public submissions create a `submitted` (never auto-`verified`) `MeasurementProfile`.

## 4. Tailoring Orders & Snapshots

- `Order` belongs to an `Organization` and `Customer`, uses `DecimalField` for monetary values, and tracks status transitions via `orders.services.transition_order_status`.
- Every transition is recorded atomically in `OrderStatusEvent`.
- When an order is linked to a measurement profile and confirmed, a frozen `measurement_snapshot` JSON payload captures the profile version, unit system, and field values at confirmation time.

## 5. Future AI / Camera Measurement Boundary

AI-assisted camera measurement is explicitly **not implemented** in Phase 0/1. It is gated behind `FEATURE_CAMERA_MEASUREMENTS=False` and isolated behind `apps/backend/measurements/camera_boundary.py` for Phase 4 implementation (explicit consent, guided capture, pose estimation, calibration, and human review).
