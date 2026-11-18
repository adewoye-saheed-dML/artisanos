# ArtisanOS API Contract (`/api/v1/`)

All authenticated browser requests use `HttpOnly` cookies (`access_token`, `refresh_token`) plus `X-CSRFToken` on unsafe methods. API/test clients may also use `Authorization: Bearer <token>`. Tenant-scoped endpoints require `X-Organization-Id: <organization-uuid>`.

OpenAPI schema and Swagger UI are served at:
- `GET /api/v1/schema/`
- `GET /api/v1/docs/`

## Health
- `GET /api/v1/health/` — Database connectivity and feature flag status.

## Authentication (`/api/v1/auth/`)
- `GET /api/v1/auth/csrf/` — Issues `csrftoken` cookie.
- `POST /api/v1/auth/register/` — Creates user and optionally creates initial organization + owner membership; sets auth cookies.
- `POST /api/v1/auth/login/` — Authenticates email/password; sets auth cookies and returns user + memberships.
- `POST /api/v1/auth/logout/` — Clears auth cookies and blacklists/invalidates refresh token if present.
- `POST /api/v1/auth/refresh/` — Refreshes `access_token` cookie using `refresh_token` cookie.
- `GET /api/v1/auth/me/` — Returns current user and active organization memberships.
- `POST /api/v1/auth/password-reset/` — Foundation endpoint for password reset requests.

## Organizations & Dashboard
- `GET /api/v1/organizations/` — List organizations where user has active membership.
- `POST /api/v1/organizations/` — Create a new organization and assign creator as `owner`.
- `GET / PATCH /api/v1/organizations/{id}/` — View or update organization profile (`owner`/`manager` for PATCH).
- `GET /api/v1/organizations/{id}/members/` — List organization members.
- `PATCH /api/v1/organizations/{id}/members/{member_id}/` — Update member role or suspend/reactivate (`owner`/`manager` RBAC).
- `GET / POST /api/v1/organizations/{id}/invitations/` — List or create expiring team invitations.
- `POST /api/v1/organizations/{id}/invitations/{invite_id}/revoke/` — Revoke a pending invitation.
- `GET /api/v1/public/invitations/{token}/` — Publicly inspect an invitation token.
- `POST /api/v1/public/invitations/{token}/accept/` — Accept an invitation (existing or new user) and issue auth cookies.
- `GET /api/v1/dashboard/summary/` — Real database-backed counts, upcoming appointments, and recent orders/customers for `X-Organization-Id`.
- `GET /api/v1/analytics/overview/?months=6` — Real PostgreSQL aggregates (monthly revenue/deposits, order status funnel, top garments, production & measurement health).
- `GET /api/v1/analytics/export/customers/` — Formula-safe CSV export of organization customers (`owner`/`manager`).
- `GET /api/v1/analytics/export/orders/` — Formula-safe CSV export of organization orders (`owner`/`manager`).

## Customers (`/api/v1/customers/`)
- `GET /api/v1/customers/` — Paginated list with `?search=` and `?is_archived=`.
- `POST /api/v1/customers/` — Create customer in active organization.
- `GET / PATCH / DELETE /api/v1/customers/{id}/` — Retrieve, update, or archive (`DELETE` soft-archives `is_archived=True`).

## Measurement Templates (`/api/v1/measurement-templates/`)
- `GET /api/v1/measurement-templates/` — List system templates (`Standard Tailoring`, `Standard Shoemaking`, `Standard Leatherwork`) + active organization custom templates with latest published version & fields.
- `POST /api/v1/measurement-templates/` — Create organization-owned template + v1 + fields (`owner`/`manager`).
- `GET / PATCH /api/v1/measurement-templates/{id}/` — Retrieve or update template metadata.
- `POST /api/v1/measurement-templates/{id}/versions/` — Publish a new template version with fields.
- `POST /api/v1/measurement-templates/{id}/clone/` — Clone any system or workspace template into a customizable workspace template.

## Measurements, Requests & Fit Passport Portability
- `GET /api/v1/customers/{customer_id}/measurements/` — List all measurement profiles (and historical versions) for a customer.
- `POST /api/v1/customers/{customer_id}/measurements/` — Record a new measurement profile.
- `POST /api/v1/customers/{customer_id}/measurements/import-from-share/` — Import a customer's consented Fit Passport share link/token as `source="imported"`, `status="needs_review"`.
- `GET / PATCH /api/v1/customers/{customer_id}/measurements/{profile_id}/` — Inspect a profile or create a revised version (`PATCH` creates a new version when values/unit change so history is never silently overwritten).
- `POST /api/v1/customers/{customer_id}/measurements/{profile_id}/verify/` — Mark a profile `verified` with `verified_by` and `verified_at`.
- `GET / POST /api/v1/measurement-requests/` — List or generate expiring measurement request links.
- `POST /api/v1/measurement-requests/{id}/revoke/` — Revoke a pending measurement request.
- `GET / POST /api/v1/public/measurement-requests/{token}/` — Public customer measurement submission portal (no internal IDs exposed).
- `GET / POST /api/v1/measurement-shares/` — List or create consented, expiring Fit Passport share links for verified profiles.
- `POST /api/v1/measurement-shares/{id}/revoke/` — Revoke an active Fit Passport share link.
- `GET /api/v1/public/fit/{token}/` — Public read-only Fit Passport (no contact PII or internal IDs exposed).
- `GET / POST /api/v1/customers/{customer_id}/media/` — List or upload consented guided reference photos (restricted to `owner`/`manager`/`artisan`, 30-day retention).
- `GET /api/v1/customers/{customer_id}/media/{asset_id}/content/` — Stream protected image bytes with `Cache-Control: private, no-store` and append a `viewed` `MediaAccessLog`.
- `GET /api/v1/customers/{customer_id}/media/{asset_id}/audit/` — Inspect upload/view/delete/purge access trail.
- `DELETE /api/v1/customers/{customer_id}/media/{asset_id}/` — Physically delete raw photo from disk and mark deleted.
- `POST /api/v1/public/measurement-requests/{token}/photos/` — Optional consented front/side photo upload attached to an active measurement request.

## Orders (`/api/v1/orders/`)
- `GET /api/v1/orders/` — List organization orders (`?status=`, `?customer=`, `?search=`).
- `POST /api/v1/orders/` — Create order with initial `OrderStatusEvent`.
- `GET / PATCH /api/v1/orders/{id}/` — Retrieve or update order fields (non-status metadata, measurement link).
- `POST /api/v1/orders/{id}/transition/` — Validated status transition + `OrderStatusEvent` + snapshot freeze on confirmation.
- `GET /api/v1/orders/{id}/timeline/` — Chronological `OrderStatusEvent` history.

## Production (`/api/v1/production/`)
- `GET /api/v1/production/board/` — Kanban board grouping active orders (`confirmed`, `in_production`, `fitting`, `ready`) with task completion and alteration counts.
- `GET / POST /api/v1/production/tasks/` — List or create production checklist tasks and alteration flags.
- `GET / PATCH / DELETE /api/v1/production/tasks/{id}/` — Retrieve, update status/assignee, or delete a production task.
- `POST /api/v1/production/orders/{order_id}/seed-checklist/` — Populate the standard 5-step tailoring checklist on an order.

## Appointments (`/api/v1/appointments/`)
- `GET / POST /api/v1/appointments/` — List (supports `?from=`, `?to=`, `?customer=`, `?order=`, `?status=`) or schedule fittings/appointments.
- `GET / PATCH / DELETE /api/v1/appointments/{id}/` — Retrieve, edit, or delete an appointment.
- `POST /api/v1/appointments/{id}/complete/` — Mark appointment completed.
- `POST /api/v1/appointments/{id}/cancel/` — Cancel a scheduled appointment.

## Products, Inventory & Storefront
- `GET / POST /api/v1/products/` — List or create ready-made, made-to-order, or service listings (initial stock recorded as an `InventoryMovement`).
- `GET / PATCH / DELETE /api/v1/products/{id}/` — Retrieve, update non-stock metadata (`stock_quantity` is read-only), or archive (`DELETE`).
- `POST /api/v1/products/{id}/adjust-inventory/` — Atomically adjust stock and append an immutable `InventoryMovement` (triggers low-stock notification when `<= 2`).
- `GET /api/v1/products/{id}/movements/` — Immutable inventory ledger history for a product.
- `POST /api/v1/products/{id}/variants/` — Add size/color variants.
- `GET / PATCH /api/v1/storefront/settings/` — Manage organization public storefront profile.
- `GET / PATCH /api/v1/storefront/inquiries/` — View and update incoming public buyer inquiries.
- `GET /api/v1/storefronts/{slug}/` — Unauthenticated public storefront profile and published products.
- `POST /api/v1/storefronts/{slug}/inquiries/` — Public buyer inquiry submission (creates in-app notification).

## Notifications (`/api/v1/notifications/`)
- `GET /api/v1/notifications/` — List workspace notifications and `unread_count`.
- `POST /api/v1/notifications/{id}/read/` — Mark single notification read.
- `POST /api/v1/notifications/read-all/` — Mark all visible workspace notifications read.

## Subscriptions, Billing & Webhooks
- `GET /api/v1/subscriptions/plans/` — List active SaaS plans (`Starter`, `Growth`, `Professional`).
- `GET /api/v1/subscriptions/overview/` — Active subscription, live workspace usage vs entitlements, and recent `PaymentTransaction`s.
- `POST /api/v1/subscriptions/checkout/` — Initiate a plan change or pending Paystack checkout transaction (`owner`/`manager`).
- `POST /api/v1/webhooks/paystack/` — Constant-time HMAC-SHA512 verified Paystack webhook handler (idempotently verifies amount/currency and upgrades subscription).

## Marketplace Discovery (Public)
- `GET /api/v1/marketplace/storefronts/` — Public discovery of active, published artisan storefronts (`?search=`, `?category=`, `?city=`).
- `GET /api/v1/marketplace/products/` — Public discovery of published products across active storefronts (`?search=`, `?category=`, `?product_type=`).

## Platform Administration (`/api/v1/platform-admin/`, restricted to `is_platform_admin=True`)
- `GET /api/v1/platform-admin/overview/` — Platform-wide tenant/user/customer/order counts.
- `GET /api/v1/platform-admin/organizations/` — Search/inspect organizations with plans and usage counts.
- `POST /api/v1/platform-admin/organizations/{org_id}/suspend/` — Suspend organization with mandatory audit reason.
- `POST /api/v1/platform-admin/organizations/{org_id}/reactivate/` — Reactivate organization with audit reason.
- `POST /api/v1/platform-admin/organizations/{org_id}/assign-plan/` — Assign subscription plan with audit trail.
- `GET /api/v1/platform-admin/audit-logs/` — Immutable audit log feed.
