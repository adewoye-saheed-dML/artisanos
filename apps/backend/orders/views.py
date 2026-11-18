from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenancy import TenantScopedMixin

from .models import Order
from .serializers import (
    OrderCreateSerializer,
    OrderDetailSerializer,
    OrderListSerializer,
    OrderStatusEventSerializer,
    OrderTransitionSerializer,
    OrderUpdateSerializer,
)
from .services import create_order, transition_order_status


class OrderViewSet(
    TenantScopedMixin,
    mixins.ListModelMixin,
    mixins.CreateModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Organization-scoped tailoring order management, transitions, and timeline."""

    filterset_fields = ["status", "customer", "payment_status", "assigned_to"]
    search_fields = ["order_number", "garment_type", "customer__full_name"]
    ordering_fields = ["created_at", "expected_completion_date", "quoted_amount"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Order.objects.none()
        org = self.get_organization()
        return (
            Order.objects.filter(organization=org)
            .select_related("customer", "assigned_to", "measurement_profile", "created_by")
            .prefetch_related("status_events__changed_by")
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        if self.action == "list":
            return OrderListSerializer
        if self.action == "create":
            return OrderCreateSerializer
        if self.action in {"update", "partial_update"}:
            return OrderUpdateSerializer
        return OrderDetailSerializer

    def create(self, request, *args, **kwargs):
        org = self.get_organization()
        serializer = OrderCreateSerializer(data=request.data, context=self.get_serializer_context())
        serializer.is_valid(raise_exception=True)
        order = create_order(
            organization=org,
            created_by=request.user,
            validated_data=serializer.validated_data,
        )
        order = self.get_queryset().get(id=order.id)
        return Response(OrderDetailSerializer(order).data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = OrderUpdateSerializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        order = serializer.save()
        order = self.get_queryset().get(id=order.id)
        return Response(OrderDetailSerializer(order).data)

    @action(detail=True, methods=["post"])
    def transition(self, request, pk=None):
        order = self.get_object()
        serializer = OrderTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = transition_order_status(
            order=order,
            to_status=serializer.validated_data["to_status"],
            actor=request.user,
            notes=serializer.validated_data.get("notes", ""),
        )
        updated = self.get_queryset().get(id=updated.id)
        return Response(OrderDetailSerializer(updated).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=["get"])
    def timeline(self, request, pk=None):
        order = self.get_object()
        events = order.status_events.select_related("changed_by").order_by("created_at")
        return Response(OrderStatusEventSerializer(events, many=True).data)
