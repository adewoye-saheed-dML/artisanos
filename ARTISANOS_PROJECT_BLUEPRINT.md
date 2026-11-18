# ArtisanOS — Project Blueprint

**Working name:** ArtisanOS  
**Product category:** Multi-tenant SaaS for measurement-based artisan businesses  
**Initial vertical:** Tailoring  
**Expansion verticals:** Shoemaking, leatherwork, fashion accessories and other custom-measurement services  
**Reference product:** Mezer (reusable customer measurement records and camera-assisted measurement estimates)

---

## 1. Product vision

ArtisanOS is a business platform that helps artisans capture and manage customer measurements, manage customer relationships, quote and fulfil custom orders, track production, arrange fittings, and sell ready-made products online.

Tailoring is the first vertical, not the limit of the product. The platform must use configurable measurement templates so different artisan categories can use the same customer, order, product and business-management foundation.

### Product promise

**Measure customers. Manage work. Sell products. Grow the business.**

### Main user groups

1. **Artisan/business owner:** owns a workspace, manages its members, customers, measurements, orders, products, storefront and subscription.
2. **Artisan/team member:** performs assigned work and accesses only the workspace areas permitted by their role.
3. **Customer:** can receive a secure measurement request, submit or update measurements, view permitted order information and buy products.
4. **Platform administrator:** manages the SaaS platform, business accounts, plans, platform configuration and support operations.
5. **Marketplace buyer:** discovers public artisan storefronts and products. A buyer may also be an existing customer of an artisan.

---

## 2. Product principles

- **Multi-tenant from day one:** every business-owned record belongs to an organization/workspace. Enforce tenant scoping in the backend, not only in the frontend.
- **Configurable measurements:** measurements are data-driven, not hard-coded only for tailors.
- **Human-confirmed fit data:** camera outputs are estimates. Important measurements must be reviewed and confirmed by the artisan/customer before production.
- **Customer privacy:** collect explicit consent before camera/photo capture; explain what is stored and why; restrict access; support deletion and retention policies.
- **Mobile-first:** artisans and customers will often use phones. Forms, camera flows, customer records and order updates must work well on small screens.
- **Business workflow first:** the first release must solve customer records, measurements and orders before attempting a sophisticated AI model or full multi-vendor checkout.
- **Auditable changes:** preserve measurement history and record who changed/confirmed important values.

---

## 3. Main product areas

### A. Authentication and onboarding

- Sign up, sign in, sign out and password reset.
- Create an artisan business/workspace during onboarding.
- Select business category: Tailor, Shoemaker, Leatherworker, Other.
- Set business name, contact information, address/location, currency and preferred measurement unit.
- Invite team members in a later iteration.
- Provide an organization switcher for users who belong to more than one workspace.

### B. Multi-tenant organization management

- Organization/workspace profile.
- Memberships and roles: Owner, Administrator/Manager, Artisan/Worker, Sales Assistant.
- Subscription plan and usage limits.
- Workspace settings and business-specific measurement templates.
- Backend permission checks for every organization-scoped operation.

### C. Dashboard

Initial dashboard cards:
- Total customers.
- Active orders.
- Orders awaiting measurements.
- Orders in production.
- Orders ready for collection/delivery.
- Monthly sales/revenue (only from recorded transactions).
- Upcoming fittings/appointments.

Dashboard lists:
- Recent orders.
- Upcoming appointments.
- Recent customer activity.

Do not display fabricated statistics. Empty states should guide a new business to add its first customer or order.

### D. Customer management

- Create, view, edit and archive customers.
- Store name, phone, email (optional), address (optional), notes and preferred contact method.
- Search and filter customers.
- Customer detail page with measurement profiles, measurement history, orders, appointments and notes.
- Keep customer data scoped to the owning workspace in the first release.
- Add customer consent records where photos or camera capture are used.

### E. Measurement engine (the core differentiator)

Build a generic measurement model.

**Measurement template** defines a set of fields for an artisan category or a custom template. Each field should have:
- key/slug;
- display name;
- description/instructions;
- unit type (length, circumference, width, angle, free numeric or text where justified);
- default unit and validation range;
- whether required;
- display order;
- optional capture guidance or diagram reference.

**Initial tailoring template examples:** neck, chest/bust, waist, hip, shoulder width, sleeve length, armhole, bicep, wrist, shirt length, trouser waist, thigh, knee, inseam, outseam, ankle.

**Initial shoemaking template examples:** left/right foot length, foot width, ball girth, instep girth, heel width, ankle girth and preferred shoe style. Confirm the exact list with practicing shoemakers before treating it as authoritative.

**Measurement record/profile:**
- customer;
- organization/workspace;
- template and template version;
- measurement values;
- unit system (cm/in);
- source (manual, customer-submitted, camera-assisted, imported);
- status (draft, submitted, needs_review, verified, superseded);
- created by and verified by;
- measured/recorded date;
- notes;
- optional related media with consent metadata.

Keep historical versions. Updating a customer's current measurements must not silently overwrite measurements already used for a confirmed order.

### F. Measurement requests and customer portal

- Artisan creates a measurement request for a customer.
- Generate a secure, random, expiring link/token.
- Customer opens the link without needing to create an account for the first MVP.
- Customer can enter measurements manually and optionally upload permitted reference photos.
- Submission is marked `submitted` or `needs_review`, never automatically `verified`.
- Artisan reviews, edits if necessary, and verifies the submitted record.
- Prevent token reuse after expiry/revocation and avoid exposing internal customer IDs in public links.

### G. Tailoring and custom orders

Order information:
- customer;
- order number;
- service/product description;
- selected measurement profile/version;
- garment type and options;
- quoted amount and agreed amount;
- deposit/balance/payment status;
- expected completion date;
- assigned artisan/team member;
- customer instructions and internal notes;
- delivery/collection method.

Suggested order statuses:
`draft → awaiting_measurements → quoted → confirmed → in_production → fitting → ready → completed`

Additional terminal statuses: `cancelled`, `on_hold`.

Keep an order activity timeline showing status changes, notes and important actions. An order should retain a snapshot/reference to the measurement version used when it was confirmed.

### H. Production tracking

- Production board grouped by status.
- Assign order to an artisan/worker.
- Add task/checklist items (cutting, sewing, finishing, quality check, etc.).
- Record fitting date and fitting notes.
- Flag alteration requests and link them to the order.
- Mark ready for collection/delivery.

Start with a simple Kanban/list board. Advanced workflow automation can come later.

### I. Appointments and fittings

- Create, edit and cancel appointments.
- Link appointment to customer and optionally an order.
- Date, time, duration, location and notes.
- Upcoming appointments list and basic calendar view.
- Later: customer reminders by email, SMS or WhatsApp provider.

### J. Products, inventory and storefront

- Product CRUD with name, description, category, price, images, sizes/variants, stock quantity and publication status.
- Mark products as ready-made, made-to-order or service listings.
- Give each organization a public storefront slug/URL.
- Public storefront shows business profile and published products.
- Product detail page and inquiry/contact action.
- Basic cart/checkout can follow after core product listing works.
- Inventory adjustments should be recorded, not silently overwritten.

### K. Marketplace

Later stage:
- Public discovery of artisan storefronts and products.
- Search and filtering by category, location, price and availability.
- Seller verification and storefront reviews.
- Buyer accounts, cart, checkout, order tracking and dispute/support workflows.
- Multi-seller checkout and payout ledger only after payment, refunds, seller onboarding and reconciliation are designed properly.

### L. AI-assisted camera measurement

Treat this as a dedicated product workstream, not a quick form feature.

**First camera milestone:** build a guided capture experience that checks camera permission, framing, lighting, pose, distance and image quality. Allow the customer to capture guided front/side views and save them only with explicit consent. The first version may simply attach the images to a pending measurement review; do not pretend that it has calculated accurate measurements.

**Later computer-vision milestone:** use pose landmarks and segmentation as inputs to a calibrated measurement model. MediaPipe Pose Landmarker can detect body landmarks from images/video and return 2D/3D landmark information, but pose landmarks alone are not body circumferences or tailor-ready measurements. A separate model and calibration/validation process is required.

Possible capture requirements to test:
- camera positioned at a known distance and height;
- full body visible, with correct framing;
- front and side views (potentially additional views);
- known user height and a calibration reference or other validated scale method;
- consistent clothing and pose instructions;
- image-quality and landmark-confidence checks;
- human review and correction before production.

**Validation requirement:** compare estimates against professional tape measurements across a diverse, consented test dataset. Report measurement-specific error and failure rates. Do not advertise a universal accuracy claim without independent validation.

**Privacy requirement:** avoid retaining raw images longer than necessary; store consent, access logs and deletion state; limit who can view images; use secure object storage; do not use customer images for model training without separate explicit consent.

### M. Notifications

- In-app notifications for order and measurement events.
- Email for account and order events.
- Later: SMS and WhatsApp notifications through an approved provider.
- Notification preferences per business/customer.

### N. SaaS subscriptions and platform administration

Subscription foundation:
- Plans such as Starter, Growth and Professional.
- Plan entitlements/limits (users, customers, monthly measurement requests, products, storage, locations).
- Subscription status, billing period and usage tracking.
- Trial support if desired.
- Payment integration through a Nigerian payment provider such as Paystack after the product workflows are stable.
- Verify payment webhooks on the backend; never trust frontend payment success alone.

Platform admin:
- list/search organizations;
- view plan and subscription status;
- suspend/reactivate an organization with audit trail;
- support overview and usage metrics;
- manage plan definitions.

---

## 4. Suggested data model (first design pass)

Core entities:

- `User`
- `Organization`
- `Membership` (user, organization, role, status)
- `Subscription` and `Plan`
- `Customer` (organization-scoped)
- `MeasurementTemplate` (system or organization-owned)
- `MeasurementTemplateVersion`
- `MeasurementField`
- `MeasurementProfile`
- `MeasurementValue`
- `MeasurementRequest`
- `ConsentRecord`
- `MediaAsset`
- `Order`
- `OrderItem`
- `OrderMeasurementSnapshot` or a stable reference to a verified profile version
- `OrderStatusEvent`
- `ProductionTask`
- `Appointment`
- `Product`
- `ProductVariant`
- `InventoryMovement`
- `Storefront`
- `PaymentTransaction`
- `Notification`
- `AuditLog`

Important constraints:
- Every organization-owned object has an organization foreign key.
- Validate that related customer, order, product and measurement records belong to the same organization.
- Add database indexes for common organization-scoped searches.
- Use soft archive where appropriate, but do not use soft deletion as a substitute for a real personal-data deletion policy.
- Use decimal fields for money, never floating-point.
- Store dates/times with timezone awareness.

---

## 5. API design conventions

Use a versioned API prefix such as `/api/v1/`.

Initial endpoint groups:

- `/auth/` — register, login, logout, refresh, password reset, current user.
- `/organizations/` — create/list/update workspace, memberships, roles.
- `/customers/` — customer CRUD and search.
- `/measurement-templates/` — list templates, create custom templates, manage versions/fields.
- `/customers/{id}/measurements/` — measurement profiles and history.
- `/measurement-requests/` — create, revoke and inspect requests.
- `/public/measurement-requests/{token}/` — customer submission via secure token.
- `/orders/` — order CRUD, status transitions and activity timeline.
- `/production/` — task assignment and production updates.
- `/appointments/` — calendar and appointment CRUD.
- `/products/` — product CRUD and inventory.
- `/storefronts/{slug}/` — public storefront and published products.
- `/subscriptions/` — plan, subscription and usage overview.
- `/admin/` — platform administration (restricted to platform admins).

Use consistent pagination, filtering, validation errors and response formats. Document endpoints with OpenAPI/Swagger.

---

## 6. Recommended implementation stack

### Frontend
- Next.js (App Router) + TypeScript.
- Tailwind CSS + shadcn/ui.
- React Hook Form + Zod for forms and validation.
- TanStack Query for server state if needed; avoid adding state libraries without a use case.
- Responsive dashboard shell and reusable table/form/dialog components.

### Backend
- Python + Django + Django REST Framework.
- PostgreSQL.
- Simple JWT or a carefully implemented secure cookie-based JWT flow; tokens must not be stored in localStorage.
- Django filters and OpenAPI schema generation.
- Celery + Redis when asynchronous tasks are introduced.

### Development and deployment
- Monorepo with separate `apps/backend` and `apps/frontend`.
- Docker Compose for local PostgreSQL and Redis.
- `.env.example` with placeholders only; never commit secrets.
- Local media storage in development; S3-compatible object storage in production.
- CI checks: backend tests, frontend lint/typecheck/build, migration check.

---

## 7. Delivery roadmap

### Phase 0 — Foundation (today)
- Repository and documentation.
- Backend and frontend scaffolding.
- Docker Compose for PostgreSQL (Redis optional initially).
- Environment configuration.
- Health endpoint and API schema.
- Frontend app shell and responsive dashboard layout.
- Basic registration/login contract or a clearly isolated auth stub if full auth cannot be completed today.

### Phase 1 — Working tailoring MVP
- Organization onboarding and tenant scoping.
- Customer management.
- Tailoring measurement template.
- Manual measurement profiles and history.
- Measurement request link and customer submission.
- Tailoring orders and status timeline.
- Basic dashboard with real database data.

### Phase 2 — Business operations
- Production board and task assignment.
- Appointments and fittings.
- Team members and role permissions.
- Product catalogue, inventory and public storefront.
- Email notifications.

### Phase 3 — Artisan expansion
- Shoemaker and leatherworker templates.
- Custom measurement template builder.
- Category-specific order forms and workflows.
- Customer measurement portability/sharing with explicit permission.

### Phase 4 — Camera-assisted measurement
- Guided camera capture and quality checks.
- Consent and secure media lifecycle.
- Pose landmark extraction.
- Calibrated measurement estimation model.
- Human confirmation, test dataset and accuracy reporting.

### Phase 5 — Commerce and SaaS monetization
- Subscription plans and usage enforcement.
- Paystack integration and webhook verification.
- Marketplace discovery and buyer accounts.
- Checkout, refunds, reconciliation and seller payouts.
- Reviews, seller verification and support/dispute workflows.

### Phase 6 — Scale
- Mobile app/PWA enhancements.
- Analytics and business reports.
- Multi-location organizations.
- Integrations and public API.
- Operational monitoring, backups, security reviews and performance testing.

---

## 8. Definition of done for today's MVP session

A demo is successful when the following flow works against the real backend/database:

1. A new user registers and creates a tailor workspace.
2. The user signs in and sees the workspace dashboard.
3. The user creates a customer.
4. The user opens that customer and records a tailoring measurement profile in centimetres.
5. The user can edit the profile and see its history or at least its latest saved version.
6. The user creates an order for that customer and associates the measurement profile.
7. The user updates the order status and sees the change in the order timeline/list.
8. Data remains isolated from another organization.
9. Frontend validation and backend validation both work.
10. README explains how to run both applications and tests.

A polished UI with mocked data does not satisfy this definition of done.

---

## 9. Antigravity CLI setup (Ubuntu/Linux)

The official Antigravity CLI documentation currently provides this Linux/macOS installation command:

```bash
curl -fsSL https://antigravity.google/cli/install.sh | bash
```

Then make sure the default install directory is on PATH and verify the binary:

```bash
export PATH="$HOME/.local/bin:$PATH"
agy --version
```

Create the project workspace and launch the agent:

```bash
mkdir -p ~/projects/artisan-os
cd ~/projects/artisan-os
git init
agy
```

Authenticate when prompted. Within the Antigravity CLI, use its interactive session to review the implementation plan and diffs. Start with the Phase 0 prompt below rather than asking the agent to build every future module at once.

---

## 10. First Antigravity task prompt

Paste this into the Antigravity CLI after entering the empty `artisan-os` project directory:

```text
You are the lead engineer building ArtisanOS, a production-minded multi-tenant SaaS for measurement-based artisan businesses. Tailoring is the first vertical; shoemakers, leatherworkers and other artisans must be supported later through configurable measurement templates.

Read the project requirements in ARTISANOS_PROJECT_BLUEPRINT.md if the file exists. If it does not exist, use the specification in this prompt. Do not attempt to implement every roadmap phase now.

TODAY'S SCOPE: Phase 0 foundation plus the first working vertical slice for organizations, customers, manual tailoring measurements and orders.

TECH STACK:
- Monorepo.
- Backend: Python, Django, Django REST Framework, PostgreSQL.
- Frontend: Next.js App Router, TypeScript, Tailwind CSS, shadcn/ui.
- Docker Compose for local PostgreSQL; Redis/Celery may be scaffolded only if genuinely needed now.
- OpenAPI API documentation.

NON-NEGOTIABLE ARCHITECTURE:
1. Multi-tenancy from the beginning. Every organization-owned record must be scoped to an organization and every API query/mutation must enforce membership and role permissions server-side.
2. Never trust organization IDs supplied by the browser without verifying membership.
3. Use configurable measurement templates and measurement values. Do not hard-code the database schema exclusively for tailoring.
4. Preserve measurement history. An order must reference the measurement profile/version used when it was confirmed.
5. Use decimal types for money and timezone-aware timestamps.
6. Do not store authentication tokens in localStorage. Use a secure, carefully documented authentication approach.
7. Do not commit secrets. Create .env.example with placeholders.
8. Do not fabricate dashboard numbers or use mock data for features represented as implemented.
9. Do not claim camera measurements are implemented. Camera/AI is a later phase; scaffold only a clearly labelled future integration boundary if needed.
10. Write tests for tenant isolation and core business rules.

FIRST, inspect the empty/current repository and produce a short implementation plan. Then scaffold:
- apps/backend: Django project and apps for accounts, organizations, customers, measurement_templates, measurements and orders.
- apps/frontend: Next.js TypeScript app with a responsive dashboard shell and pages for dashboard, customers, customer detail/measurements, and orders.
- infrastructure or root Docker Compose for PostgreSQL.
- docs/architecture.md, docs/api-contract.md and README.md.

CORE DATA MODEL:
- User.
- Organization.
- Membership with roles Owner, Manager and Artisan.
- Customer scoped to Organization.
- MeasurementTemplate and versioned MeasurementTemplateVersion/MeasurementField.
- MeasurementProfile linked to Customer, Organization and template version.
- MeasurementValue linked to MeasurementProfile and field.
- Order linked to Customer and Organization, with a stable reference to the measurement profile/version used.
- OrderStatusEvent for audit/history.

INITIAL TAILORING FIELDS:
neck, chest, waist, hip, shoulder_width, sleeve_length, armhole, bicep, wrist, shirt_length, trouser_waist, thigh, knee, inseam, outseam, ankle.
Support cm and inches. Seed these as a versioned tailoring template. Design the template system so a shoemaker template can be added without schema changes.

CORE WORKFLOW TO IMPLEMENT:
1. Register/login and create a workspace.
2. Create/list/search customers.
3. Open a customer profile and create/edit a manual measurement profile.
4. Display measurement history/version information.
5. Create an order for a customer and associate a measurement profile/version.
6. Update the order status through a validated status-transition service and record an OrderStatusEvent.
7. Show actual database-backed counts and recent orders on the dashboard.

FRONTEND EXPECTATIONS:
- Professional, clean SaaS interface; mobile responsive.
- Sidebar navigation on desktop and usable mobile navigation.
- Clear empty states, loading states and error states.
- Forms with client-side validation and server error display.
- Accessible labels, keyboard-friendly controls and sensible contrast.
- Do not spend the entire session on decorative UI before the backend workflow works.

ENGINEERING PROCESS:
- Keep backend and frontend runnable independently and document exact commands.
- Add migrations and seed/demo data command if useful.
- Add backend tests for organization isolation, role permissions, measurement validation and order status history.
- Add frontend lint, typecheck and build scripts.
- Run tests, lint, typecheck and build; fix failures before declaring completion.
- Do not silently skip errors. Report any incomplete item and why.
- Keep code modular but avoid unnecessary abstraction or premature microservices.
- After the first plan, implement in small verified milestones. Show changed files and commands run.

At the end, provide:
1. What works end-to-end.
2. What is scaffolded but not implemented.
3. Exact local startup commands.
4. Test results.
5. Known security or product gaps.
6. The next three highest-priority tasks.
```

---

## 11. Working rules for the project

- Build and verify one complete flow at a time.
- Do not ask the coding agent to generate the entire SaaS in one giant pass.
- Review database migrations, permission checks and payment code carefully.
- Keep a `docs/DECISIONS.md` file for important architecture decisions.
- Keep the AI measurement feature behind a feature flag until it has been validated.
- Use realistic demo data, clearly identified as demo data.
- Before launch, complete security testing, backup/restore testing, privacy review, payment reconciliation and production monitoring.

**The first milestone is not “all features exist.” It is “one tailor can run a real customer-to-measurement-to-order workflow without mock data.”**
