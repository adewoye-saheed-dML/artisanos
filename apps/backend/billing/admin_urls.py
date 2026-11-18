from django.urls import path

from .admin_views import (
    PlatformAdminAssignPlanView,
    PlatformAdminAuditLogListView,
    PlatformAdminOrganizationListView,
    PlatformAdminOverviewView,
    PlatformAdminReactivateOrgView,
    PlatformAdminSuspendOrgView,
)

urlpatterns = [
    path("overview/", PlatformAdminOverviewView.as_view(), name="platform-admin-overview"),
    path("organizations/", PlatformAdminOrganizationListView.as_view(), name="platform-admin-orgs"),
    path(
        "organizations/<uuid:org_id>/suspend/",
        PlatformAdminSuspendOrgView.as_view(),
        name="platform-admin-suspend",
    ),
    path(
        "organizations/<uuid:org_id>/reactivate/",
        PlatformAdminReactivateOrgView.as_view(),
        name="platform-admin-reactivate",
    ),
    path(
        "organizations/<uuid:org_id>/assign-plan/",
        PlatformAdminAssignPlanView.as_view(),
        name="platform-admin-assign-plan",
    ),
    path("audit-logs/", PlatformAdminAuditLogListView.as_view(), name="platform-admin-audit-logs"),
]
