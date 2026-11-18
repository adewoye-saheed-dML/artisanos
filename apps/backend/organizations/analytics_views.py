import csv
import io
from datetime import timedelta
from decimal import Decimal

from django.db.models import Count, Sum
from django.db.models.functions import Coalesce, TruncMonth
from django.http import HttpResponse
from django.utils import timezone
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework import exceptions, serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, resolve_organization_context
from customers.models import Customer
from measurements.models import MeasurementProfile, MeasurementShareLink
from orders.models import Order
from organizations.models import Membership
from production.models import ProductionTask


def _csv_safe(value) -> str:
    """Neutralize spreadsheet formula injection on exported CSV cells."""
    text = "" if value is None else str(value)
    if text and text[0] in ("=", "+", "-", "@", "\t", "\r"):
        return f"'{text}"
    return text


class StatusCountSerializer(serializers.Serializer):
    status = serializers.CharField()
    count = serializers.IntegerField()


class MonthlyRevenuePointSerializer(serializers.Serializer):
    month = serializers.CharField()
    orders_count = serializers.IntegerField()
    quoted_total = serializers.CharField()
    deposits_collected = serializers.CharField()


class TopGarmentSerializer(serializers.Serializer):
    garment_type = serializers.CharField()
    count = serializers.IntegerField()
    quoted_total = serializers.CharField()


class ProductionAnalyticsSerializer(serializers.Serializer):
    total_tasks = serializers.IntegerField()
    completed_tasks = serializers.IntegerField()
    completion_rate_pct = serializers.IntegerField()
    open_alterations = serializers.IntegerField()


class MeasurementAnalyticsSerializer(serializers.Serializer):
    total_profiles = serializers.IntegerField()
    verified_profiles = serializers.IntegerField()
    manual_profiles = serializers.IntegerField()
    customer_submitted_profiles = serializers.IntegerField()
    imported_profiles = serializers.IntegerField()
    active_share_links = serializers.IntegerField()


class AnalyticsOverviewResponseSerializer(serializers.Serializer):
    currency = serializers.CharField()
    months = serializers.IntegerField()
    order_status_breakdown = StatusCountSerializer(many=True)
    monthly_revenue_trend = MonthlyRevenuePointSerializer(many=True)
    top_garment_types = TopGarmentSerializer(many=True)
    production = ProductionAnalyticsSerializer()
    measurements = MeasurementAnalyticsSerializer()


class AnalyticsOverviewView(APIView):
    """Real PostgreSQL-backed workspace analytics and operational reports."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: AnalyticsOverviewResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        try:
            months = max(1, min(12, int(request.query_params.get("months", 6))))
        except ValueError:
            months = 6

        now = timezone.now()
        since = (now - timedelta(days=months * 31)).replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        orders_qs = Order.objects.filter(organization=org)
        status_rows = list(
            orders_qs.values("status").annotate(count=Count("id")).order_by("-count", "status")
        )

        monthly_rows = (
            orders_qs.filter(created_at__gte=since)
            .exclude(status=Order.Status.CANCELLED)
            .annotate(month_dt=TruncMonth("created_at"))
            .values("month_dt")
            .annotate(
                orders_count=Count("id"),
                quoted_total=Coalesce(Sum("quoted_amount"), Decimal("0.00")),
                deposits_collected=Coalesce(Sum("deposit_amount"), Decimal("0.00")),
            )
            .order_by("month_dt")
        )
        monthly_trend = [
            {
                "month": row["month_dt"].strftime("%Y-%m"),
                "orders_count": row["orders_count"],
                "quoted_total": str(row["quoted_total"]),
                "deposits_collected": str(row["deposits_collected"]),
            }
            for row in monthly_rows
            if row["month_dt"] is not None
        ]

        top_garments = [
            {
                "garment_type": row["garment_type"],
                "count": row["count"],
                "quoted_total": str(row["quoted_total"]),
            }
            for row in orders_qs.exclude(status=Order.Status.CANCELLED)
            .values("garment_type")
            .annotate(
                count=Count("id"),
                quoted_total=Coalesce(Sum("quoted_amount"), Decimal("0.00")),
            )
            .order_by("-count", "-quoted_total")[:6]
        ]

        tasks_qs = ProductionTask.objects.filter(organization=org)
        total_tasks = tasks_qs.count()
        completed_tasks = tasks_qs.filter(status=ProductionTask.Status.DONE).count()
        completion_rate = int(round((completed_tasks / total_tasks) * 100)) if total_tasks > 0 else 0
        open_alterations = tasks_qs.filter(is_alteration=True).exclude(
            status=ProductionTask.Status.DONE
        ).count()

        profiles_qs = MeasurementProfile.objects.filter(organization=org)
        active_shares = MeasurementShareLink.objects.filter(
            organization=org,
            status=MeasurementShareLink.Status.ACTIVE,
            expires_at__gt=now,
        ).count()

        return Response(
            {
                "currency": org.currency,
                "months": months,
                "order_status_breakdown": status_rows,
                "monthly_revenue_trend": monthly_trend,
                "top_garment_types": top_garments,
                "production": {
                    "total_tasks": total_tasks,
                    "completed_tasks": completed_tasks,
                    "completion_rate_pct": completion_rate,
                    "open_alterations": open_alterations,
                },
                "measurements": {
                    "total_profiles": profiles_qs.count(),
                    "verified_profiles": profiles_qs.filter(
                        status=MeasurementProfile.Status.VERIFIED
                    ).count(),
                    "manual_profiles": profiles_qs.filter(
                        source=MeasurementProfile.Source.MANUAL
                    ).count(),
                    "customer_submitted_profiles": profiles_qs.filter(
                        source=MeasurementProfile.Source.CUSTOMER_SUBMITTED
                    ).count(),
                    "imported_profiles": profiles_qs.filter(
                        source=MeasurementProfile.Source.IMPORTED
                    ).count(),
                    "active_share_links": active_shares,
                },
            }
        )


def _require_export_role(request):
    membership = resolve_organization_context(request)
    if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
        raise exceptions.PermissionDenied("Only organization owners or managers can export workspace CSV reports.")
    return membership.organization


class CustomerCsvExportView(APIView):
    """Export organization customers as a formula-safe CSV file (owners & managers only)."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.STR, description="CSV report")})
    def get(self, request):
        org = _require_export_role(request)
        customers = Customer.objects.filter(organization=org).order_by("-created_at")

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "Full Name",
                "Phone",
                "Email",
                "Preferred Contact",
                "Address",
                "Archived",
                "Notes",
                "Created At",
            ]
        )
        for c in customers:
            writer.writerow(
                [
                    _csv_safe(c.full_name),
                    _csv_safe(c.phone),
                    _csv_safe(c.email),
                    _csv_safe(c.preferred_contact_method),
                    _csv_safe(c.address),
                    "yes" if c.is_archived else "no",
                    _csv_safe(c.notes),
                    c.created_at.isoformat(),
                ]
            )

        resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{org.slug}-customers.csv"'
        resp["Cache-Control"] = "private, no-store"
        return resp


class OrderCsvExportView(APIView):
    """Export organization orders as a formula-safe CSV file (owners & managers only)."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: OpenApiResponse(response=OpenApiTypes.STR, description="CSV report")})
    def get(self, request):
        org = _require_export_role(request)
        orders = Order.objects.filter(organization=org).select_related("customer").order_by("-created_at")

        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(
            [
                "Order Number",
                "Customer",
                "Garment / Item",
                "Status",
                "Quoted Amount",
                "Agreed Amount",
                "Deposit Paid",
                "Currency",
                "Payment Status",
                "Delivery Method",
                "Expected Completion",
                "Created At",
            ]
        )
        for o in orders:
            writer.writerow(
                [
                    _csv_safe(o.order_number),
                    _csv_safe(o.customer.full_name),
                    _csv_safe(o.garment_type),
                    _csv_safe(o.status),
                    str(o.quoted_amount),
                    str(o.agreed_amount) if o.agreed_amount is not None else "",
                    str(o.deposit_amount),
                    _csv_safe(o.currency),
                    _csv_safe(o.payment_status),
                    _csv_safe(o.delivery_method),
                    o.expected_completion_date.isoformat() if o.expected_completion_date else "",
                    o.created_at.isoformat(),
                ]
            )

        resp = HttpResponse(buf.getvalue(), content_type="text/csv; charset=utf-8")
        resp["Content-Disposition"] = f'attachment; filename="{org.slug}-orders.csv"'
        resp["Cache-Control"] = "private, no-store"
        return resp
