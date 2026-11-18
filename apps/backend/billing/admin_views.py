from django.db import transaction
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.permissions import BasePermission
from rest_framework.response import Response
from rest_framework.views import APIView

from accounts.models import User
from customers.models import Customer
from orders.models import Order
from organizations.models import Membership, Organization

from .models import AuditLog, Plan
from .seed import seed_default_plans
from .serializers import (
    AuditLogSerializer,
    PlatformAdminActionSerializer,
    PlatformAdminAssignPlanSerializer,
    PlatformAdminOrgSummarySerializer,
    PlatformAdminOverviewSerializer,
)
from .services import get_or_create_subscription


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
