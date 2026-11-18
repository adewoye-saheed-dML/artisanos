from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from billing.views import PaystackWebhookView
from core.views import HealthCheckView
from measurements.views import PublicFitPassportView
from organizations.dashboard_views import DashboardSummaryView
from organizations.views import PublicInvitationAcceptView, PublicInvitationDetailView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/v1/health/", HealthCheckView.as_view(), name="health-check"),
    path("api/v1/schema/", SpectacularAPIView.as_view(), name="api-schema"),
    path("api/v1/docs/", SpectacularSwaggerView.as_view(url_name="api-schema"), name="api-docs"),
    path("api/v1/auth/", include("accounts.urls")),
    path("api/v1/organizations/", include("organizations.urls")),
    path(
        "api/v1/public/invitations/<str:token>/",
        PublicInvitationDetailView.as_view(),
        name="public-invitation-detail",
    ),
    path(
        "api/v1/public/invitations/<str:token>/accept/",
        PublicInvitationAcceptView.as_view(),
        name="public-invitation-accept",
    ),
    path("api/v1/dashboard/summary/", DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("api/v1/analytics/", include("organizations.analytics_urls")),
    path("api/v1/customers/", include("customers.urls")),
    path("api/v1/measurement-templates/", include("measurement_templates.urls")),
    path("api/v1/", include("measurements.urls")),
    path("api/v1/public/measurement-requests/", include("measurements.public_urls")),
    path("api/v1/public/fit/<str:token>/", PublicFitPassportView.as_view(), name="public-fit-passport"),
    path("api/v1/orders/", include("orders.urls")),
    path("api/v1/production/", include("production.urls")),
    path("api/v1/appointments/", include("appointments.urls")),
    path("api/v1/", include("catalog.urls")),
    path("api/v1/storefronts/", include("catalog.public_urls")),
    path("api/v1/marketplace/", include("catalog.marketplace_urls")),
    path("api/v1/notifications/", include("notifications.urls")),
    path("api/v1/subscriptions/", include("billing.urls")),
    path("api/v1/webhooks/paystack/", PaystackWebhookView.as_view(), name="paystack-webhook"),
    path("api/v1/platform-admin/", include("billing.admin_urls")),
]
