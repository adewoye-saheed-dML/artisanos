from django.urls import path

from .admin_views import (
    PlatformAdminApproveKYCView,
    PlatformAdminAssignPlanView,
    PlatformAdminAuditLogListView,
    PlatformAdminEscrowDisputeListView,
    PlatformAdminEscrowResolveView,
    PlatformAdminOrganizationListView,
    PlatformAdminOverviewView,
    PlatformAdminReactivateOrgView,
    PlatformAdminRejectKYCView,
    PlatformAdminSuspendOrgView,
    PlatformAdminVerificationListView,
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
    path(
        "verifications/",
        PlatformAdminVerificationListView.as_view(),
        name="platform-admin-verifications",
    ),
    path(
        "verifications/<uuid:org_id>/approve/",
        PlatformAdminApproveKYCView.as_view(),
        name="platform-admin-kyc-approve",
    ),
    path(
        "verifications/<uuid:org_id>/reject/",
        PlatformAdminRejectKYCView.as_view(),
        name="platform-admin-kyc-reject",
    ),
    path(
        "escrow/",
        PlatformAdminEscrowDisputeListView.as_view(),
        name="platform-admin-escrow-list",
    ),
    path(
        "escrow/<uuid:escrow_id>/resolve/",
        PlatformAdminEscrowResolveView.as_view(),
        name="platform-admin-escrow-resolve",
    ),
    path("audit-logs/", PlatformAdminAuditLogListView.as_view(), name="platform-admin-audit-logs"),
]
