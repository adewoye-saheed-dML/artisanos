import threading

from django.db import close_old_connections, transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from customers.models import Customer
from escrow.models import EscrowTransaction
from escrow.serializers import EscrowResolveSerializer, EscrowTransactionSerializer
from escrow.services import resolve_escrow_dispute
from locations.inec_importer import sync_full_inec_dataset
from locations.models import NigerianLGA, NigerianState, NigerianWard, PollingUnit
from locations.seed import seed_nigeria_locations
from orders.models import Order
from organizations.kyc_services import approve_artisan_kyc, reject_artisan_kyc
from organizations.models import ArtisanVerification, Membership, Organization
from organizations.serializers import ArtisanVerificationSerializer

from .models import AuditLog, Plan
from .seed import seed_default_plans
from .serializers import (
    AuditLogSerializer,
    PlatformAdminActionSerializer,
    PlatformAdminAssignPlanSerializer,
    PlatformAdminLocationSyncRequestSerializer,
    PlatformAdminLocationSyncStatusSerializer,
    PlatformAdminOrgSummarySerializer,
    PlatformAdminOverviewSerializer,
    PlatformAdminRevenueSummarySerializer,
)
from .services import get_or_create_subscription, get_platform_revenue_summary

_LOCATION_SYNC_LOCK = threading.RLock()
_LOCATION_SYNC_STATE: dict[str, object] = {
    "state": "idle",
    "mode": "",
    "last_message": "",
    "error": "",
    "started_at": None,
    "finished_at": None,
}


def _build_location_sync_payload() -> dict[str, object]:
    total_pus = PollingUnit.objects.count()
    with _LOCATION_SYNC_LOCK:
        snapshot = dict(_LOCATION_SYNC_STATE)
    snapshot.update(
        {
            "total_states": NigerianState.objects.count(),
            "total_lgas": NigerianLGA.objects.count(),
            "total_wards": NigerianWard.objects.count(),
            "total_polling_units": total_pus,
            "geolocated_polling_units": PollingUnit.objects.filter(
                latitude__isnull=False, longitude__isnull=False
            ).count(),
            "is_full_inec_loaded": total_pus >= 100000,
        }
    )
    return snapshot


def _run_full_inec_background(actor_id, skip_geo: bool) -> None:
    close_old_connections()
    try:
        def _progress(msg: str) -> None:
            with _LOCATION_SYNC_LOCK:
                _LOCATION_SYNC_STATE["last_message"] = msg

        stats = sync_full_inec_dataset(
            include_geo_enrichment=not skip_geo,
            progress_callback=_progress,
        )
        summary = (
            f"INEC sync complete: {stats['total_states']} states, {stats['total_lgas']} LGAs, "
            f"{stats['total_wards']} wards, {stats['total_polling_units']} polling units "
            f"({stats['geolocated_polling_units']} geolocated)."
        )
        AuditLog.objects.create(
            actor_id=actor_id,
            action="locations_full_inec_synced",
            target_type="Locations",
            target_id="nigeria_inec",
            reason=summary,
            metadata=stats,
        )
        with _LOCATION_SYNC_LOCK:
            _LOCATION_SYNC_STATE["state"] = "succeeded"
            _LOCATION_SYNC_STATE["last_message"] = summary
            _LOCATION_SYNC_STATE["error"] = ""
            _LOCATION_SYNC_STATE["finished_at"] = timezone.now()
    except Exception as exc:  # pragma: no cover - network/dataset runtime error
        with _LOCATION_SYNC_LOCK:
            _LOCATION_SYNC_STATE["state"] = "failed"
            _LOCATION_SYNC_STATE["error"] = str(exc)
            _LOCATION_SYNC_STATE["finished_at"] = timezone.now()
    finally:
        close_old_connections()


class IsPlatformAdmin(BasePermission):
    """Restrict platform administration strictly to users with is_platform_admin=True."""

    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_platform_admin)


class PlatformAdminOverviewView(APIView):
    """High-level SaaS platform metrics across all tenant workspaces."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: PlatformAdminOverviewSerializer})
    def get(self, request):
        total_orgs = Organization.objects.count()
        active_orgs = Organization.objects.filter(is_active=True).count()
        return Response(
            {
                "total_organizations": total_orgs,
                "active_organizations": active_orgs,
                "suspended_organizations": total_orgs - active_orgs,
                "total_users": User.objects.count(),
                "total_customers": Customer.objects.filter(is_archived=False).count(),
                "total_orders": Order.objects.count(),
            }
        )


class PlatformAdminRevenueView(APIView):
    """Multi-stream NGN platform revenue overview: Subscriptions (MRR), Spotlight Boosts, and Escrow fees."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: PlatformAdminRevenueSummarySerializer})
    def get(self, request):
        summary = get_platform_revenue_summary()
        return Response(PlatformAdminRevenueSummarySerializer(summary).data)


class PlatformAdminOrganizationListView(APIView):
    """Search and inspect all organizations, their subscription plan, and usage counts."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: PlatformAdminOrgSummarySerializer(many=True)})
    def get(self, request):
        qs = Organization.objects.annotate(
            member_count=Count("memberships", filter=Q(memberships__status=Membership.Status.ACTIVE), distinct=True),
            customer_count=Count("customers_customer_set", filter=Q(customers_customer_set__is_archived=False), distinct=True),
            order_count=Count("orders_order_set", distinct=True),
        ).order_by("-created_at")

        search = (request.query_params.get("search") or "").strip()
        if search:
            qs = qs.filter(Q(name__icontains=search) | Q(slug__icontains=search) | Q(email__icontains=search))

        rows = []
        for org in qs[:100]:
            sub = get_or_create_subscription(org)
            rows.append(
                {
                    "id": org.id,
                    "name": org.name,
                    "slug": org.slug,
                    "category": org.category,
                    "currency": org.currency,
                    "is_active": org.is_active,
                    "plan_code": sub.plan.code,
                    "plan_name": sub.plan.name,
                    "subscription_status": sub.status,
                    "member_count": org.member_count,
                    "customer_count": org.customer_count,
                    "order_count": org.order_count,
                    "created_at": org.created_at,
                }
            )
        return Response(PlatformAdminOrgSummarySerializer(rows, many=True).data)


class PlatformAdminSuspendOrgView(APIView):
    """Suspend an organization with a mandatory audit trail."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=PlatformAdminActionSerializer, responses={200: AuditLogSerializer})
    @transaction.atomic
    def post(self, request, org_id):
        org = get_object_or_404(Organization, id=org_id)
        serializer = PlatformAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org.is_active = False
        org.save(update_fields=["is_active", "updated_at"])
        log = AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="organization_suspended",
            target_type="Organization",
            target_id=str(org.id),
            reason=serializer.validated_data["reason"],
        )
        return Response(AuditLogSerializer(log).data, status=status.HTTP_200_OK)


class PlatformAdminReactivateOrgView(APIView):
    """Reactivate a suspended organization with an audit trail."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=PlatformAdminActionSerializer, responses={200: AuditLogSerializer})
    @transaction.atomic
    def post(self, request, org_id):
        org = get_object_or_404(Organization, id=org_id)
        serializer = PlatformAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        org.is_active = True
        org.save(update_fields=["is_active", "updated_at"])
        log = AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="organization_reactivated",
            target_type="Organization",
            target_id=str(org.id),
            reason=serializer.validated_data["reason"],
        )
        return Response(AuditLogSerializer(log).data, status=status.HTTP_200_OK)


class PlatformAdminAssignPlanView(APIView):
    """Manually assign a subscription plan to an organization with audit trail."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=PlatformAdminAssignPlanSerializer, responses={200: AuditLogSerializer})
    @transaction.atomic
    def post(self, request, org_id):
        org = get_object_or_404(Organization, id=org_id)
        serializer = PlatformAdminAssignPlanSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        if not Plan.objects.exists():
            seed_default_plans()
        plan = get_object_or_404(Plan, code=serializer.validated_data["plan_code"])

        sub = get_or_create_subscription(org)
        old_code = sub.plan.code
        sub.plan = plan
        sub.status = sub.Status.ACTIVE
        sub.save(update_fields=["plan", "status", "updated_at"])

        log = AuditLog.objects.create(
            organization=org,
            actor=request.user,
            action="plan_assigned_by_admin",
            target_type="Subscription",
            target_id=str(sub.id),
            reason=serializer.validated_data["reason"],
            metadata={"from_plan": old_code, "to_plan": plan.code},
        )
        return Response(AuditLogSerializer(log).data, status=status.HTTP_200_OK)


class PlatformAdminAuditLogListView(APIView):
    """List recent platform administration and billing audit events."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: AuditLogSerializer(many=True)})
    def get(self, request):
        logs = AuditLog.objects.select_related("actor", "organization").order_by("-created_at")[:100]
        return Response(AuditLogSerializer(logs, many=True).data)


class PlatformAdminVerificationListView(APIView):
    """Inspect artisan NIN/CAC KYC verification queue."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: ArtisanVerificationSerializer(many=True)})
    def get(self, request):
        status_filter = (request.query_params.get("status") or "").strip()
        qs = (
            ArtisanVerification.objects.select_related(
                "organization",
                "organization__state",
                "organization__ward",
                "organization__polling_unit",
                "submitted_by",
                "reviewed_by",
            )
            .prefetch_related("documents__uploaded_by")
            .order_by("-submitted_at")
        )
        if status_filter:
            qs = qs.filter(status=status_filter)
        return Response(ArtisanVerificationSerializer(qs[:100], many=True).data)


class PlatformAdminApproveKYCView(APIView):
    """Approve an artisan's NIN/CAC verification and auto-publish their storefront."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=PlatformAdminActionSerializer, responses={200: ArtisanVerificationSerializer})
    def post(self, request, org_id):
        org = get_object_or_404(Organization, id=org_id)
        notes = (request.data.get("reason") or request.data.get("notes") or "").strip()
        kyc = approve_artisan_kyc(organization=org, reviewer=request.user, notes=notes)
        return Response(ArtisanVerificationSerializer(kyc).data, status=status.HTTP_200_OK)


class PlatformAdminRejectKYCView(APIView):
    """Reject an artisan's KYC application with mandatory reason."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=PlatformAdminActionSerializer, responses={200: ArtisanVerificationSerializer})
    def post(self, request, org_id):
        org = get_object_or_404(Organization, id=org_id)
        serializer = PlatformAdminActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        kyc = reject_artisan_kyc(
            organization=org,
            reviewer=request.user,
            reason=serializer.validated_data["reason"],
        )
        return Response(ArtisanVerificationSerializer(kyc).data, status=status.HTTP_200_OK)


class PlatformAdminEscrowDisputeListView(APIView):
    """List escrow transactions (filterable by status, defaulting to disputed)."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: EscrowTransactionSerializer(many=True)})
    def get(self, request):
        status_filter = (request.query_params.get("status") or EscrowTransaction.Status.DISPUTED).strip()
        qs = (
            EscrowTransaction.objects.select_related("organization", "customer_user", "order")
            .prefetch_related("events__actor")
            .order_by("-created_at")
        )
        if status_filter and status_filter != "all":
            qs = qs.filter(status=status_filter)
        return Response(
            EscrowTransactionSerializer(qs[:100], many=True, context={"request": request}).data
        )


class PlatformAdminEscrowResolveView(APIView):
    """Arbitrate a disputed escrow transaction (refund customer or release to artisan)."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(request=EscrowResolveSerializer, responses={200: EscrowTransactionSerializer})
    def post(self, request, escrow_id):
        escrow = get_object_or_404(EscrowTransaction, id=escrow_id)
        serializer = EscrowResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        resolved = resolve_escrow_dispute(
            escrow=escrow,
            admin_user=request.user,
            decision=serializer.validated_data["decision"],
            reason=serializer.validated_data["reason"],
        )
        return Response(
            EscrowTransactionSerializer(resolved, context={"request": request}).data,
            status=status.HTTP_200_OK,
        )


class PlatformAdminLocationSyncStatusView(APIView):
    """Inspect live Nigerian geographic dataset counts and background INEC sync state (no Shell needed)."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(responses={200: PlatformAdminLocationSyncStatusSerializer})
    def get(self, request):
        payload = _build_location_sync_payload()
        return Response(PlatformAdminLocationSyncStatusSerializer(payload).data)


class PlatformAdminLocationSyncTriggerView(APIView):
    """Trigger baseline Nigeria location seed or full INEC dataset sync directly from Platform Admin."""

    permission_classes = [IsPlatformAdmin]

    @extend_schema(
        request=PlatformAdminLocationSyncRequestSerializer,
        responses={200: PlatformAdminLocationSyncStatusSerializer, 202: PlatformAdminLocationSyncStatusSerializer},
    )
    def post(self, request):
        serializer = PlatformAdminLocationSyncRequestSerializer(data=request.data or {})
        serializer.is_valid(raise_exception=True)
        mode = serializer.validated_data["mode"]
        skip_geo = serializer.validated_data.get("skip_geo", False)

        with _LOCATION_SYNC_LOCK:
            if _LOCATION_SYNC_STATE["state"] == "running":
                payload = _build_location_sync_payload()
                return Response(
                    PlatformAdminLocationSyncStatusSerializer(payload).data,
                    status=status.HTTP_202_ACCEPTED,
                )

        if mode == "baseline":
            now = timezone.now()
            stats = seed_nigeria_locations()
            summary = (
                f"Baseline Nigeria locations ready: {stats['total_states']} states, "
                f"{stats['total_lgas']} LGAs, {stats['total_wards']} wards, "
                f"{stats['total_polling_units']} polling units."
            )
            AuditLog.objects.create(
                actor=request.user,
                action="locations_baseline_seeded",
                target_type="Locations",
                target_id="nigeria_baseline",
                reason=summary,
                metadata=stats,
            )
            with _LOCATION_SYNC_LOCK:
                _LOCATION_SYNC_STATE.update(
                    {
                        "state": "succeeded",
                        "mode": "baseline",
                        "last_message": summary,
                        "error": "",
                        "started_at": now,
                        "finished_at": timezone.now(),
                    }
                )
            payload = _build_location_sync_payload()
            return Response(
                PlatformAdminLocationSyncStatusSerializer(payload).data,
                status=status.HTTP_200_OK,
            )

        with _LOCATION_SYNC_LOCK:
            _LOCATION_SYNC_STATE.update(
                {
                    "state": "running",
                    "mode": "full_inec",
                    "last_message": "Starting background INEC dataset download & bulk import...",
                    "error": "",
                    "started_at": timezone.now(),
                    "finished_at": None,
                }
            )
        worker = threading.Thread(
            target=_run_full_inec_background,
            args=(request.user.id, skip_geo),
            daemon=True,
        )
        worker.start()
        payload = _build_location_sync_payload()
        return Response(
            PlatformAdminLocationSyncStatusSerializer(payload).data,
            status=status.HTTP_202_ACCEPTED,
        )
