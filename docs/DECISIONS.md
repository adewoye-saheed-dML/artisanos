# Architectural Decisions Log

## ADR-001: Cookie-Based JWT via Same-Origin Next.js Proxy
- **Decision**: Issue JWT access and refresh tokens in `HttpOnly`, `SameSite=Lax` cookies rather than returning tokens for `localStorage`, and proxy `/api/v1/*` through Next.js rewrites to Django.
- **Rationale**: Eliminates XSS exposure of tokens in `localStorage` and prevents cross-origin cookie issues between ports `3000` and `8000` in local development.

## ADR-002: Header-Scoped Multi-Tenancy Verified Against Active Membership
- **Decision**: Require `X-Organization-Id` on all tenant-scoped API calls and resolve `request.organization` / `request.membership` strictly through a database lookup on `Membership(user=request.user, organization_id=..., status="active")`.
- **Rationale**: Users can belong to multiple artisan workspaces and switch cleanly without re-authenticating, while preventing cross-tenant access even if a client tampers with `X-Organization-Id` or nested resource IDs.

## ADR-003: Immutable Measurement Profile Revisions
- **Decision**: Editing measurement values on an existing `MeasurementProfile` creates a new `MeasurementProfile` row (`version_number + 1`, `parent_profile` linked) and marks the previous version `superseded` (`is_latest=False`), rather than mutating existing `MeasurementValue` rows in place.
- **Rationale**: Preserves complete measurement history and guarantees confirmed orders never have their historical measurements silently altered. Additionally, `Order.measurement_snapshot` freezes confirmed values at order confirmation.

## ADR-004: Configurable Versioned Measurement Templates
- **Decision**: Represent measurement schemas as `MeasurementTemplate` -> `MeasurementTemplateVersion` -> `MeasurementField` rows instead of garment-specific columns on a table.
- **Rationale**: Allows tailoring, shoemaking, leatherwork, and custom artisan templates to share the exact same persistence, validation, and UI form engine.
