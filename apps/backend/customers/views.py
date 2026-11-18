from rest_framework import exceptions, status, viewsets
from rest_framework.response import Response

from core.tenancy import TenantScopedMixin
from organizations.models import Membership

from .models import Customer
from .serializers import CustomerSerializer


class CustomerViewSet(TenantScopedMixin, viewsets.ModelViewSet):
    """Organization-scoped customer CRUD and search."""

    serializer_class = CustomerSerializer
    filterset_fields = ["is_archived", "preferred_contact_method"]
    search_fields = ["full_name", "phone", "email"]
    ordering_fields = ["full_name", "created_at", "updated_at"]

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Customer.objects.none()
        org = self.get_organization()
        qs = Customer.objects.filter(organization=org).select_related("created_by")
        # Default to active customers unless is_archived query param is explicitly provided
        if self.action == "list" and "is_archived" not in self.request.query_params:
            qs = qs.filter(is_archived=False)
        return qs

    def perform_create(self, serializer):
        org = self.get_organization()
        from billing.services import enforce_plan_limit

        enforce_plan_limit(org, "customers")
        serializer.save(organization=org, created_by=self.request.user)

    def perform_update(self, serializer):
        if "is_archived" in serializer.validated_data:
            membership = self.get_membership()
            if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
                raise exceptions.PermissionDenied("Only owners or managers can archive or restore customers.")
        serializer.save()

    def destroy(self, request, *args, **kwargs):
        membership = self.get_membership()
        if membership.role not in {Membership.Role.OWNER, Membership.Role.MANAGER}:
            raise exceptions.PermissionDenied("Only owners or managers can archive customers.")
        customer = self.get_object()
        customer.is_archived = True
        customer.save(update_fields=["is_archived", "updated_at"])
        return Response(CustomerSerializer(customer).data, status=status.HTTP_200_OK)
