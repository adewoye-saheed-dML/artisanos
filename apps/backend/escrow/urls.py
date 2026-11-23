from django.urls import path

from .views import (
    EscrowCancelView,
    EscrowDetailView,
    EscrowDisputeView,
    EscrowFundView,
    EscrowListCreateView,
    EscrowReleaseView,
    EscrowSubmitWorkView,
)

urlpatterns = [
    path("", EscrowListCreateView.as_view(), name="escrow-list-create"),
    path("<uuid:escrow_id>/", EscrowDetailView.as_view(), name="escrow-detail"),
    path("<uuid:escrow_id>/fund/", EscrowFundView.as_view(), name="escrow-fund"),
    path("<uuid:escrow_id>/submit-work/", EscrowSubmitWorkView.as_view(), name="escrow-submit-work"),
    path("<uuid:escrow_id>/release/", EscrowReleaseView.as_view(), name="escrow-release"),
    path("<uuid:escrow_id>/dispute/", EscrowDisputeView.as_view(), name="escrow-dispute"),
    path("<uuid:escrow_id>/cancel/", EscrowCancelView.as_view(), name="escrow-cancel"),
]
