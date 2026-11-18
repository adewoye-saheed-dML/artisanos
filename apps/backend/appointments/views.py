from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from core.tenancy import TenantScopedMixin

from .models import Appointment
from .serializers import AppointmentSerializer


class AppointmentViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Organization-scoped fittings and appointment scheduling."""

    serializer_class = AppointmentSerializer
    filterset_fields = ["status", "customer", "order", "appointment_type", "assigned_to"]
    search_fields = ["title", "location", "notes", "customer__full_name"]
    ordering_fields = ["scheduled_at", "created_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Appointment.objects.none()
        org = self.get_organization()
        qs = (
            Appointment.objects.filter(organization=org)
            .select_related("customer", "order", "assigned_to")
            .order_by("scheduled_at")
        )
        date_from = self.request.query_params.get("from")
        date_to = self.request.query_params.get("to")
        if date_from:
            parsed = parse_datetime(date_from)
            if parsed:
                qs = qs.filter(scheduled_at__gte=parsed)
        if date_to:
            parsed = parse_datetime(date_to)
            if parsed:
                qs = qs.filter(scheduled_at__lte=parsed)
        return qs

    @extend_schema(request=None, responses={200: AppointmentSerializer})
    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = Appointment.Status.CANCELLED
        appointment.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)

    @extend_schema(request=None, responses={200: AppointmentSerializer})
    @action(detail=True, methods=["post"])
    def complete(self, request, pk=None):
        appointment = self.get_object()
        appointment.status = Appointment.Status.COMPLETED
        appointment.save(update_fields=["status", "updated_at"])
        return Response(AppointmentSerializer(appointment).data, status=status.HTTP_200_OK)
