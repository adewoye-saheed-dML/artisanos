from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from appointments.serializers import AppointmentSerializer
from core.tenancy import ActiveOrganizationPermission, resolve_organization_context
from customers.models import Customer
from customers.serializers import CustomerSerializer
from orders.models import Order
from orders.serializers import OrderListSerializer


class DashboardOrganizationSerializer(serializers.Serializer):
    id = serializers.UUIDField()
    name = serializers.CharField()
    category = serializers.CharField()
    currency = serializers.CharField()
    preferred_unit = serializers.CharField()


class DashboardMetricsSerializer(serializers.Serializer):
    total_customers = serializers.IntegerField()
    active_orders = serializers.IntegerField()
    orders_awaiting_measurements = serializers.IntegerField()
    orders_in_production = serializers.IntegerField()
    orders_ready = serializers.IntegerField()
    upcoming_appointments = serializers.IntegerField()
    monthly_recorded_deposits = serializers.CharField()


class DashboardSummaryResponseSerializer(serializers.Serializer):
    organization = DashboardOrganizationSerializer()
    metrics = DashboardMetricsSerializer()
    recent_orders = OrderListSerializer(many=True)
    recent_customers = CustomerSerializer(many=True)
    upcoming_appointments = AppointmentSerializer(many=True)


class DashboardSummaryView(APIView):
    """Real database-backed workspace overview metrics and recent activity."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: DashboardSummaryResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        customers_qs = Customer.objects.filter(organization=org, is_archived=False)
        orders_qs = Order.objects.filter(organization=org).select_related("customer")
        upcoming_appts_qs = (
            Appointment.objects.filter(
                organization=org,
                status=Appointment.Status.SCHEDULED,
                scheduled_at__gte=now,
            )
            .select_related("customer", "order", "assigned_to")
            .order_by("scheduled_at")
        )

        active_statuses = [
            Order.Status.DRAFT,
            Order.Status.AWAITING_MEASUREMENTS,
            Order.Status.QUOTED,
            Order.Status.CONFIRMED,
            Order.Status.IN_PRODUCTION,
            Order.Status.FITTING,
            Order.Status.READY,
        ]

        monthly_revenue = (
            orders_qs.filter(created_at__gte=month_start)
            .exclude(status=Order.Status.CANCELLED)
            .aggregate(total=Coalesce(Sum("deposit_amount"), Decimal("0.00")))["total"]
        )

        recent_orders = orders_qs.order_by("-created_at")[:5]
        recent_customers = customers_qs.order_by("-created_at")[:5]
        upcoming_appointments = upcoming_appts_qs[:5]

        return Response(
            {
                "organization": {
                    "id": str(org.id),
                    "name": org.name,
                    "category": org.category,
                    "currency": org.currency,
                    "preferred_unit": org.preferred_unit,
                },
                "metrics": {
                    "total_customers": customers_qs.count(),
                    "active_orders": orders_qs.filter(status__in=active_statuses).count(),
                    "orders_awaiting_measurements": orders_qs.filter(
                        status=Order.Status.AWAITING_MEASUREMENTS
                    ).count(),
                    "orders_in_production": orders_qs.filter(
                        status__in=[Order.Status.IN_PRODUCTION, Order.Status.FITTING]
                    ).count(),
                    "orders_ready": orders_qs.filter(status=Order.Status.READY).count(),
                    "upcoming_appointments": upcoming_appts_qs.count(),
                    "monthly_recorded_deposits": str(monthly_revenue),
                },
                "recent_orders": OrderListSerializer(recent_orders, many=True).data,
                "recent_customers": CustomerSerializer(recent_customers, many=True).data,
                "upcoming_appointments": AppointmentSerializer(upcoming_appointments, many=True).data,
            }
        )
