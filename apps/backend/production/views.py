from django.db.models import Count, Q
from django.shortcuts import get_object_or_404
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.response import Response
from rest_framework.views import APIView

from core.tenancy import ActiveOrganizationPermission, TenantScopedMixin, resolve_organization_context
from orders.models import Order
from orders.services import ALLOWED_TRANSITIONS

from .models import ProductionTask
from .serializers import ProductionBoardResponseSerializer, ProductionTaskSerializer
from .services import seed_standard_checklist

BOARD_COLUMNS = [
    (Order.Status.CONFIRMED, "Confirmed"),
    (Order.Status.IN_PRODUCTION, "In Production"),
    (Order.Status.FITTING, "Fitting"),
    (Order.Status.READY, "Ready for Collection"),
]


class ProductionTaskViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Manage production checklist tasks and alteration flags for workspace orders."""

    serializer_class = ProductionTaskSerializer
    filterset_fields = ["order", "status", "stage", "assigned_to", "is_alteration"]
    search_fields = ["title", "notes", "order__order_number"]
    ordering_fields = ["display_order", "due_date", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return ProductionTask.objects.none()
        org = self.get_organization()
        return (
            ProductionTask.objects.filter(organization=org)
            .select_related("order", "assigned_to", "created_by")
            .order_by("display_order", "created_at")
        )


class SeedOrderChecklistView(APIView):
    """Populate a standard tailoring production checklist for an order."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(
        request=None,
        responses={201: ProductionTaskSerializer(many=True)},
    )
    def post(self, request, order_id):
        org = resolve_organization_context(request).organization
        order = get_object_or_404(Order, id=order_id, organization=org)
        seed_standard_checklist(organization=org, order=order, actor=request.user)
        tasks = order.production_tasks.select_related("order", "assigned_to", "created_by").order_by(
            "display_order", "created_at"
        )
        return Response(ProductionTaskSerializer(tasks, many=True).data, status=status.HTTP_201_CREATED)


class ProductionBoardView(APIView):
    """Kanban board grouping active production orders with real task completion counts."""

    permission_classes = [ActiveOrganizationPermission]

    @extend_schema(responses={200: ProductionBoardResponseSerializer})
    def get(self, request):
        org = resolve_organization_context(request).organization
        board_statuses = [col[0] for col in BOARD_COLUMNS]

        orders = (
            Order.objects.filter(organization=org, status__in=board_statuses)
            .select_related("customer", "assigned_to")
            .annotate(
                total_tasks=Count("production_tasks"),
                completed_tasks=Count(
                    "production_tasks",
                    filter=Q(production_tasks__status=ProductionTask.Status.DONE),
                ),
                alteration_tasks=Count(
                    "production_tasks",
                    filter=Q(production_tasks__is_alteration=True),
                ),
            )
            .order_by("expected_completion_date", "-created_at")
        )

        grouped: dict[str, list[dict]] = {col[0]: [] for col in BOARD_COLUMNS}
        for order in orders:
            grouped[order.status].append(
                {
                    "id": order.id,
                    "order_number": order.order_number,
                    "customer": order.customer_id,
                    "customer_name": order.customer.full_name,
                    "garment_type": order.garment_type,
                    "status": order.status,
                    "expected_completion_date": order.expected_completion_date,
                    "assigned_to": order.assigned_to_id,
                    "assigned_to_name": order.assigned_to.full_name if order.assigned_to else None,
                    "total_tasks": order.total_tasks,
                    "completed_tasks": order.completed_tasks,
                    "alteration_tasks": order.alteration_tasks,
                    "allowed_next_statuses": sorted(ALLOWED_TRANSITIONS.get(order.status, set())),
                }
            )

        columns = [
            {"status": status_key, "label": label, "orders": grouped[status_key]}
            for status_key, label in BOARD_COLUMNS
        ]
        serializer = ProductionBoardResponseSerializer({"columns": columns})
        return Response(serializer.data)
